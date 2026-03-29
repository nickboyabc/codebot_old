"""
用户管理 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, List

from core.rbac import Permission, has_permission
from database.auth_db import get_auth_db
from api.deps import get_current_user, TokenData, require_permission


router = APIRouter(prefix="/api/users", tags=["用户管理"])


# ── 请求模型 ────────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(default="user")


class UpdateUserStatusRequest(BaseModel):
    """更新用户状态请求"""
    reason: Optional[str] = None


# ── 路由 ────────────────────────────────────────────────────────────────────

@router.get("/")
async def list_users(
    user: TokenData = Depends(require_permission(Permission.MANAGE_USERS))
):
    """
    获取用户列表（仅管理员）

    返回所有用户的信息
    """
    db = get_auth_db()
    users = db.list_users()

    # 不返回密码哈希
    safe_users = []
    for u in users:
        safe_users.append({
            "id": u["id"],
            "username": u["username"],
            "role": u["role"],
            "status": u["status"],
            "created_at": u["created_at"],
            "updated_at": u["updated_at"],
            "last_login": u["last_login"],
            "created_by": u.get("created_by"),
            "suspended_reason": u.get("suspended_reason")
        })

    return {
        "success": True,
        "data": {
            "items": safe_users,
            "total": len(safe_users)
        }
    }


@router.post("/")
async def create_user(
    req: CreateUserRequest,
    current_user: TokenData = Depends(require_permission(Permission.MANAGE_USERS)),
    request: Request = None
):
    """
    创建用户（仅管理员）

    - 用户名需3-50字符
    - 密码需6-100字符
    - 角色可选 user/admin，默认为 user
    """
    db = get_auth_db()

    # 检查用户名是否已存在
    existing = db.get_user(req.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 验证角色
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="无效的角色")

    # 创建用户（新建用户直接为 active 状态）
    password_hash = db.password_hash(req.password)
    user_id = db.create_user(
        username=req.username,
        password_hash=password_hash,
        role=req.role,
        status="active",
        created_by=current_user.sub
    )

    # 记录审计日志
    db.log_audit(
        username=current_user.username,
        action="create_user",
        resource="user",
        details=f"创建用户: {req.username}, 角色: {req.role}",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent")
    )

    return {
        "success": True,
        "message": "用户创建成功",
        "data": {
            "id": user_id,
            "username": req.username,
            "role": req.role,
            "status": "active"
        }
    }


@router.put("/{user_id}/approve")
async def approve_user(
    user_id: int,
    current_user: TokenData = Depends(require_permission(Permission.MANAGE_USERS)),
    request: Request = None
):
    """
    审批通过用户（仅管理员）

    - 将用户状态从 pending 改为 active
    """
    db = get_auth_db()

    # 获取目标用户
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"用户状态不是 pending，当前状态: {user['status']}")

    # 更新状态
    db.update_user_status(user_id, "active")

    # 记录审计日志
    db.log_audit(
        username=current_user.username,
        action="approve_user",
        resource="user",
        details=f"审批通过用户: {user['username']} (ID: {user_id})",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent")
    )

    return {
        "success": True,
        "message": f"用户 {user['username']} 已审批通过"
    }


@router.put("/{user_id}/reject")
async def reject_user(
    user_id: int,
    reason: str = "",
    current_user: TokenData = Depends(require_permission(Permission.MANAGE_USERS)),
    request: Request = None
):
    """
    拒绝用户注册（仅管理员）

    - 将用户状态从 pending 改为 rejected
    """
    db = get_auth_db()

    # 获取目标用户
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"用户状态不是 pending，当前状态: {user['status']}")

    # 更新状态
    db.update_user_status(user_id, "rejected", reason or "管理员拒绝")

    # 记录审计日志
    db.log_audit(
        username=current_user.username,
        action="reject_user",
        resource="user",
        details=f"拒绝用户: {user['username']} (ID: {user_id}), 原因: {reason or '未填写'}",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent")
    )

    return {
        "success": True,
        "message": f"用户 {user['username']} 已拒绝"
    }


@router.put("/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    reason: str = "",
    current_user: TokenData = Depends(require_permission(Permission.MANAGE_USERS)),
    request: Request = None
):
    """
    停用用户（仅管理员）

    - 将用户状态从 active 改为 suspended
    - 需要填写停用原因
    """
    db = get_auth_db()

    # 获取目标用户
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user["status"] != "active":
        raise HTTPException(status_code=400, detail=f"用户状态不是 active，当前状态: {user['status']}")

    # 不能停用自己
    if user["id"] == current_user.sub:
        raise HTTPException(status_code=400, detail="不能停用自己")

    # 更新状态
    db.update_user_status(user_id, "suspended", reason or "管理员停用")

    # 撤销该用户的所有会话
    db.revoke_all_user_sessions(user_id)

    # 记录审计日志
    db.log_audit(
        username=current_user.username,
        action="suspend_user",
        resource="user",
        details=f"停用用户: {user['username']} (ID: {user_id}), 原因: {reason or '未填写'}",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent")
    )

    return {
        "success": True,
        "message": f"用户 {user['username']} 已停用"
    }


@router.put("/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_user: TokenData = Depends(require_permission(Permission.MANAGE_USERS)),
    request: Request = None
):
    """
    激活/恢复用户（仅管理员）

    - 将用户状态从 suspended 改为 active
    """
    db = get_auth_db()

    # 获取目标用户
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user["status"] != "suspended":
        raise HTTPException(status_code=400, detail=f"用户状态不是 suspended，当前状态: {user['status']}")

    # 更新状态
    db.update_user_status(user_id, "active")

    # 记录审计日志
    db.log_audit(
        username=current_user.username,
        action="activate_user",
        resource="user",
        details=f"激活用户: {user['username']} (ID: {user_id})",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent")
    )

    return {
        "success": True,
        "message": f"用户 {user['username']} 已激活"
    }


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: TokenData = Depends(require_permission(Permission.MANAGE_USERS)),
    request: Request = None
):
    """
    删除用户（仅管理员）

    - 删除用户及其所有会话
    - 不能删除自己
    """
    db = get_auth_db()

    # 获取目标用户
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不能删除自己
    if user["id"] == current_user.sub:
        raise HTTPException(status_code=400, detail="不能删除自己")

    username = user["username"]

    # 撤销所有会话
    db.revoke_all_user_sessions(user_id)

    # 删除用户
    db.delete_user(user_id)

    # 记录审计日志
    db.log_audit(
        username=current_user.username,
        action="delete_user",
        resource="user",
        details=f"删除用户: {username} (ID: {user_id})",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent")
    )

    return {
        "success": True,
        "message": f"用户 {username} 已删除"
    }


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    user: TokenData = Depends(require_permission(Permission.MANAGE_USERS))
):
    """
    获取指定用户详情（仅管理员）
    """
    db = get_auth_db()
    db_user = db.get_user_by_id(user_id)

    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "success": True,
        "data": {
            "id": db_user["id"],
            "username": db_user["username"],
            "role": db_user["role"],
            "status": db_user["status"],
            "created_at": db_user["created_at"],
            "updated_at": db_user["updated_at"],
            "last_login": db_user["last_login"],
            "created_by": db_user.get("created_by"),
            "suspended_reason": db_user.get("suspended_reason")
        }
    }


# ── 辅助函数 ────────────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    """获取客户端IP地址"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"

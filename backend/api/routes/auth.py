"""
认证 API 路由
"""
import time
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

from core.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
    REFRESH_TOKEN_EXPIRE_DAYS
)
from core.rbac import get_role_permissions
from database.auth_db import get_auth_db, AuthDatabase
from api.deps import get_current_user, TokenData


router = APIRouter(prefix="/api/auth", tags=["认证"])


# ── 登录限流 ────────────────────────────────────────────────────────────────

class RateLimiter:
    """简单的内存限流器"""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # {key: [(timestamp, count), ...]}
        self._requests = defaultdict(list)

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        检查是否允许请求
        Returns: (is_allowed, remaining_requests)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # 清理过期记录
        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        # 检查是否超限
        if len(self._requests[key]) >= self.max_requests:
            return False, 0

        # 记录本次请求
        self._requests[key].append(now)
        remaining = self.max_requests - len(self._requests[key])
        return True, remaining

    def get_retry_after(self, key: str) -> int:
        """获取需要等待的秒数"""
        if not self._requests[key]:
            return 0
        oldest = min(self._requests[key])
        elapsed = time.time() - oldest
        return max(0, int(self.window_seconds - elapsed))


# 全局限流器实例（按IP限流）
_login_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
# 全局限流器实例（按用户名限流，防止特定用户被暴力破解）
_user_login_limiter = RateLimiter(max_requests=10, window_seconds=300)


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


# ── 请求模型 ────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """验证密码强度：至少8字符，包含字母和数字"""
        if len(v) < 8:
            raise ValueError("密码至少需要8个字符")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("密码必须包含字母")
        if not re.search(r"[0-9]", v):
            raise ValueError("密码必须包含数字")
        return v


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class RefreshRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """验证密码强度：至少8字符，包含字母和数字"""
        if len(v) < 8:
            raise ValueError("密码至少需要8个字符")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("密码必须包含字母")
        if not re.search(r"[0-9]", v):
            raise ValueError("密码必须包含数字")
        return v


class LogoutRequest(BaseModel):
    """登出请求"""
    refresh_token: Optional[str] = None


# ── 路由 ────────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(req: RegisterRequest, request: Request):
    """
    用户注册

    - 用户名需3-50字符
    - 密码需6-100字符
    - 注册后状态为 pending，需管理员审核
    """
    db = get_auth_db()

    # 检查用户名是否已存在
    existing = db.get_user(req.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建用户（状态为 pending）
    password_hash = db.password_hash(req.password)
    user_id = db.create_user(
        username=req.username,
        password_hash=password_hash,
        role="user",
        status="pending"
    )

    # 记录审计日志
    db.log_audit(
        username=req.username,
        action="register",
        resource="auth",
        details=f"新用户注册: {req.username}",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent")
    )

    return {
        "success": True,
        "message": "注册成功，请等待管理员审核",
        "data": {
            "user_id": user_id,
            "username": req.username,
            "status": "pending"
        }
    }


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """
    用户登录

    - 验证用户名和密码
    - 验证用户状态（pending 状态不能登录）
    - 返回 access_token 和 refresh_token
    """
    client_ip = _get_client_ip(request)

    # IP级别限流检查（防止IP暴力破解）
    ip_allowed, ip_remaining = _login_rate_limiter.is_allowed(client_ip)
    if not ip_allowed:
        retry_after = _login_rate_limiter.get_retry_after(client_ip)
        return HTTPException(
            status_code=429,
            detail=f"登录尝试过于频繁，请 {retry_after} 秒后重试",
            headers={"Retry-After": str(retry_after)}
        )

    # 用户名级别限流检查（防止特定用户被暴力破解）
    user_allowed, user_remaining = _user_login_limiter.is_allowed(req.username)
    if not user_allowed:
        retry_after = _user_login_limiter.get_retry_after(req.username)
        return HTTPException(
            status_code=429,
            detail=f"登录尝试过于频繁，请 {retry_after} 秒后重试",
            headers={"Retry-After": str(retry_after)}
        )

    db = get_auth_db()

    # 获取用户
    user = db.get_user(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 验证密码
    if not db.verify_password(req.password, user["password_hash"]):
        # 记录失败的登录尝试
        db.log_audit(
            username=req.username,
            action="login_failed",
            resource="auth",
            details="密码错误",
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent")
        )
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 检查用户状态
    if user["status"] == "pending":
        raise HTTPException(
            status_code=403,
            detail="账号等待审核中，请联系管理员"
        )
    if user["status"] == "suspended":
        reason = user.get("suspended_reason") or "未知原因"
        raise HTTPException(
            status_code=403,
            detail=f"账号已被停用: {reason}"
        )
    if user["status"] == "rejected":
        raise HTTPException(
            status_code=403,
            detail="账号已被拒绝，请联系管理员"
        )

    # 更新最后登录时间
    db.update_last_login(user["id"])

    # 创建 Token
    token_data = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"]
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # 存储 refresh token
    from datetime import datetime, timedelta, timezone
    expires_at = (datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).isoformat()
    db.create_session(user["id"], refresh_token, expires_at)

    # 记录审计日志
    db.log_audit(
        username=user["username"],
        action="login",
        resource="auth",
        details=f"用户登录成功",
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent")
    )

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "status": user["status"]
            }
        }
    }


@router.post("/logout")
async def logout(
    req: LogoutRequest,
    user: TokenData = Depends(get_current_user),
    request: Request = None
):
    """
    用户登出

    - 撤销 refresh_token（如果提供）
    - 记录审计日志
    """
    db = get_auth_db()

    # 撤销 refresh token
    if req and req.refresh_token:
        db.revoke_session(req.refresh_token)

    # 记录审计日志
    if request:
        db.log_audit(
            username=user.username,
            action="logout",
            resource="auth",
            details="用户登出",
            ip_address=_get_client_ip(request),
            user_agent=request.headers.get("user-agent")
        )

    return {
        "success": True,
        "message": "登出成功"
    }


@router.get("/me")
async def get_me(user: TokenData = Depends(get_current_user)):
    """
    获取当前用户信息
    """
    db = get_auth_db()
    db_user = db.get_user_by_id(user.sub)

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
            "last_login": db_user["last_login"],
            "permissions": get_role_permissions(db_user["role"])
        }
    }


@router.post("/refresh")
async def refresh_token(req: RefreshRequest):
    """
    刷新访问令牌

    - 验证 refresh_token
    - 检查会话是否有效
    - 颁发新的 access_token
    """
    db = get_auth_db()

    # 验证 refresh token
    if not verify_token(req.refresh_token, "refresh"):
        raise HTTPException(status_code=401, detail="刷新令牌无效或已过期")

    # 检查会话
    session = db.get_session_by_token(req.refresh_token)
    if not session:
        raise HTTPException(status_code=401, detail="会话已失效")

    # 获取用户
    user = db.get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    if user["status"] != "active":
        raise HTTPException(
            status_code=403,
            detail=f"用户状态异常: {user['status']}"
        )

    # 创建新的 access token
    token_data = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"]
    }
    access_token = create_access_token(token_data)

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 3600
        }
    }


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    user: TokenData = Depends(get_current_user),
    request: Request = None
):
    """
    修改密码
    """
    db = get_auth_db()

    # 获取用户
    db_user = db.get_user_by_id(user.sub)
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 验证旧密码
    if not db.verify_password(req.old_password, db_user["password_hash"]):
        raise HTTPException(status_code=400, detail="旧密码错误")

    # 更新密码
    new_hash = db.password_hash(req.new_password)
    cursor = db.conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_hash, user.sub)
    )
    db.conn.commit()

    # 撤销所有现有会话（强制重新登录）
    db.revoke_all_user_sessions(user.sub)

    # 记录审计日志
    if request:
        db.log_audit(
            username=user.username,
            action="change_password",
            resource="auth",
            details="用户修改密码",
            ip_address=_get_client_ip(request),
            user_agent=request.headers.get("user-agent")
        )

    return {
        "success": True,
        "message": "密码修改成功，请重新登录"
    }


@router.get("/permissions")
async def get_my_permissions(user: TokenData = Depends(get_current_user)):
    """
    获取当前用户的权限列表
    """
    return {
        "success": True,
        "data": {
            "permissions": get_role_permissions(user.role)
        }
    }


# ── 辅助函数 ────────────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    """获取客户端IP地址"""
    # 优先从 X-Forwarded-For 获取（反向代理场景）
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # 其次从 X-Real-IP 获取
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    # 最后从 direct connection 获取
    if request.client:
        return request.client.host
    return "unknown"

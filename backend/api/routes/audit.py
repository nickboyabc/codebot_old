"""
审计 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel
from typing import Optional, List

from core.rbac import Permission
from database.auth_db import get_auth_db
from api.deps import get_current_user, TokenData, require_permission


router = APIRouter(prefix="/api/audit", tags=["审计"])


# ── 查询模型 ────────────────────────────────────────────────────────────────

class AuditLogFilter(BaseModel):
    """审计日志筛选条件"""
    username: Optional[str] = None
    action: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Query(default=100, ge=1, le=500)
    offset: int = Query(default=0, ge=0)


# ── 路由 ────────────────────────────────────────────────────────────────────

@router.get("/logs")
async def get_logs(
    username: Optional[str] = Query(default=None, description="用户名"),
    action: Optional[str] = Query(default=None, description="操作类型"),
    start_date: Optional[str] = Query(default=None, description="开始日期 (ISO格式)"),
    end_date: Optional[str] = Query(default=None, description="结束日期 (ISO格式)"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: TokenData = Depends(require_permission(Permission.VIEW_AUDIT_LOGS))
):
    """
    获取审计日志列表（仅管理员）

    支持按用户名、操作类型、日期范围筛选
    """
    db = get_auth_db()

    logs = db.get_audit_logs(
        username=username,
        action=action,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )

    total = db.get_audit_logs_count(
        username=username,
        action=action,
        start_date=start_date,
        end_date=end_date
    )

    return {
        "success": True,
        "data": {
            "items": logs,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    }


@router.get("/stats")
async def get_stats(
    user: TokenData = Depends(require_permission(Permission.VIEW_STATS))
):
    """
    获取全局统计信息（仅管理员）

    - 用户统计（总数、活跃、待审核、停用）
    - 操作统计（各类型操作次数）
    - 日志统计（总数）
    """
    db = get_auth_db()
    stats = db.get_user_stats()

    return {
        "success": True,
        "data": stats
    }


@router.get("/user/{user_id}/stats")
async def get_user_stats(
    user_id: int,
    current_user: TokenData = Depends(require_permission(Permission.VIEW_STATS))
):
    """
    获取指定用户的统计信息（仅管理员）

    - 该用户的操作类型统计
    - 活跃天数
    - 总操作次数
    """
    db = get_auth_db()

    # 获取用户信息
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    stats = db.get_user_stats(username=user["username"])

    return {
        "success": True,
        "data": {
            "user_id": user_id,
            "username": user["username"],
            **stats
        }
    }


@router.get("/actions")
async def get_action_types(
    user: TokenData = Depends(require_permission(Permission.VIEW_AUDIT_LOGS))
):
    """
    获取所有操作类型列表（仅管理员）

    用于前端筛选框
    """
    db = get_auth_db()
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT DISTINCT action FROM audit_logs ORDER BY action"
    )
    actions = [row["action"] for row in cursor.fetchall()]

    return {
        "success": True,
        "data": {
            "actions": actions
        }
    }

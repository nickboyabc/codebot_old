"""
API 共享依赖
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

from core.auth import decode_token, verify_token
from core.rbac import has_permission, Permission
from database.auth_db import get_auth_db, AuthDatabase


security = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    """Token中的用户数据"""
    sub: int          # 用户ID
    username: str     # 用户名
    role: str         # 角色
    exp: int          # 过期时间


class TokenDataInternal(BaseModel):
    """内部使用的Token数据"""
    user_id: int
    username: str
    role: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    获取当前认证用户

    从 Authorization header 中提取 JWT token 并验证
    """
    # 检查是否提供了认证信息
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要提供认证信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if not verify_token(token, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无法解析令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证用户仍存在且状态正常
    user_id = payload.get("sub")
    username = payload.get("username")

    if user_id is None or username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌格式错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查用户状态
    db = get_auth_db()
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"用户状态异常: {user['status']}",
        )

    return TokenData(
        sub=user_id,
        username=username,
        role=user["role"],
        exp=payload.get("exp", 0)
    )


async def get_current_admin(
    user: TokenData = Depends(get_current_user)
) -> TokenData:
    """获取当前用户，仅限管理员"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return user


def require_permission(permission: Permission):
    """
    权限检查依赖工厂

    用法:
        @router.get("/users")
        async def list_users(
            user: TokenData = Depends(require_permission(Permission.MANAGE_USERS))
        ):
            ...
    """
    async def dependency(user: TokenData = Depends(get_current_user)):
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {permission.value}"
            )
        return user
    return dependency

"""
RBAC 权限控制
"""
from enum import Enum
from functools import wraps
from typing import Callable, List

from fastapi import HTTPException, status


class Permission(str, Enum):
    """权限枚举"""
    # 用户管理
    MANAGE_USERS = "manage_users"           # 管理用户（创建、删除、审核）
    VIEW_USERS = "view_users"               # 查看用户列表
    APPROVE_USERS = "approve_users"          # 审批用户
    SUSPEND_USERS = "suspend_users"         # 停用用户

    # 审计日志
    VIEW_AUDIT_LOGS = "view_audit_logs"    # 查看审计日志
    VIEW_STATS = "view_stats"               # 查看统计数据

    # 系统管理
    SYSTEM_CONFIG = "system_config"         # 系统配置

    # 对话相关
    CHAT = "chat"                           # 聊天
    VIEW_CONVERSATIONS = "view_conversations"  # 查看对话
    MANAGE_CONVERSATIONS = "manage_conversations"  # 管理对话

    # 记忆相关
    VIEW_MEMORIES = "view_memories"         # 查看记忆
    MANAGE_MEMORIES = "manage_memories"     # 管理记忆

    # 定时任务
    VIEW_SCHEDULED_TASKS = "view_scheduled_tasks"  # 查看定时任务
    MANAGE_SCHEDULED_TASKS = "manage_scheduled_tasks"  # 管理定时任务

    # 技能
    VIEW_SKILLS = "view_skills"             # 查看技能
    MANAGE_SKILLS = "manage_skills"         # 管理技能

    # MCP
    VIEW_MCP = "view_mcp"                   # 查看MCP配置
    MANAGE_MCP = "manage_mcp"               # 管理MCP配置

    # 沙箱
    VIEW_SANDBOX = "view_sandbox"           # 查看沙箱
    MANAGE_SANDBOX = "manage_sandbox"       # 管理沙箱


# 角色权限映射
ROLE_PERMISSIONS: dict = {
    "admin": [
        # 用户管理
        Permission.MANAGE_USERS,
        Permission.VIEW_USERS,
        Permission.APPROVE_USERS,
        Permission.SUSPEND_USERS,
        # 审计日志
        Permission.VIEW_AUDIT_LOGS,
        Permission.VIEW_STATS,
        # 系统管理
        Permission.SYSTEM_CONFIG,
        # 对话
        Permission.CHAT,
        Permission.VIEW_CONVERSATIONS,
        Permission.MANAGE_CONVERSATIONS,
        # 记忆
        Permission.VIEW_MEMORIES,
        Permission.MANAGE_MEMORIES,
        # 定时任务
        Permission.VIEW_SCHEDULED_TASKS,
        Permission.MANAGE_SCHEDULED_TASKS,
        # 技能
        Permission.VIEW_SKILLS,
        Permission.MANAGE_SKILLS,
        # MCP
        Permission.VIEW_MCP,
        Permission.MANAGE_MCP,
        # 沙箱
        Permission.VIEW_SANDBOX,
        Permission.MANAGE_SANDBOX,
    ],
    "user": [
        # 对话
        Permission.CHAT,
        Permission.VIEW_CONVERSATIONS,
        Permission.MANAGE_CONVERSATIONS,
        # 记忆
        Permission.VIEW_MEMORIES,
        Permission.MANAGE_MEMORIES,
        # 定时任务
        Permission.VIEW_SCHEDULED_TASKS,
        Permission.MANAGE_SCHEDULED_TASKS,
        # 技能
        Permission.VIEW_SKILLS,
        Permission.MANAGE_SKILLS,
        # MCP
        Permission.VIEW_MCP,
        Permission.MANAGE_MCP,
        # 沙箱
        Permission.VIEW_SANDBOX,
    ],
    "pending": [
        # 等待审核的用户几乎没有任何权限
    ],
}


def has_permission(role: str, permission: Permission) -> bool:
    """
    检查角色是否具有指定权限

    Args:
        role: 用户角色
        permission: 权限枚举值

    Returns:
        是否具有权限
    """
    if role not in ROLE_PERMISSIONS:
        return False
    return permission in ROLE_PERMISSIONS[role]


def has_any_permission(role: str, permissions: List[Permission]) -> bool:
    """
    检查角色是否具有指定权限列表中的任意一个

    Args:
        role: 用户角色
        permissions: 权限列表

    Returns:
        是否具有任意一个权限
    """
    if role not in ROLE_PERMISSIONS:
        return False
    return any(p in ROLE_PERMISSIONS[role] for p in permissions)


def has_all_permissions(role: str, permissions: List[Permission]) -> bool:
    """
    检查角色是否具有所有指定权限

    Args:
        role: 用户角色
        permissions: 权限列表

    Returns:
        是否具有所有权限
    """
    if role not in ROLE_PERMISSIONS:
        return False
    return all(p in ROLE_PERMISSIONS[role] for p in permissions)


def require_permission(permission: Permission) -> Callable:
    """
    权限检查装饰器

    用法:
        @router.post("/users")
        @require_permission(Permission.MANAGE_USERS)
        async def create_user(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 中获取 TokenData（由 Depends 注入）
            token_data = kwargs.get("user")
            if token_data is None:
                # 尝试从Depends获取
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证"
                )

            role = getattr(token_data, "role", None)
            if role is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的认证信息"
                )

            if not has_permission(role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足，需要权限: {permission.value}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_role_permissions(role: str) -> List[str]:
    """
    获取角色的所有权限

    Args:
        role: 用户角色

    Returns:
        权限字符串列表
    """
    if role not in ROLE_PERMISSIONS:
        return []
    return [p.value for p in ROLE_PERMISSIONS[role]]

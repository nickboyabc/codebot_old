"""
JWT 认证工具
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from pathlib import Path

import jwt
from jwt.exceptions import PyJWTError

from config import settings


def _get_jwt_secret() -> str:
    """获取JWT密钥，优先从环境变量读取，其次从文件读取，最后生成新的"""
    # 1. 优先从环境变量
    secret = os.environ.get("CODEBOT_JWT_SECRET", "").strip()
    if secret and len(secret) >= 32:
        return secret

    # 2. 从持久化文件读取
    secret_file = settings.DATA_DIR / ".jwt_secret"
    if secret_file.exists():
        secret = secret_file.read_text().strip()
        if secret and len(secret) >= 32:
            return secret

    # 3. 生成新的32字节随机密钥并持久化
    secret = secrets.token_hex(32)
    try:
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(secret)
    except Exception:
        pass  # 写入失败不影响运行，但下次重启会重新生成
    return secret


JWT_SECRET = _get_jwt_secret()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("CODEBOT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 默认24小时
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("CODEBOT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_access_token(
    data: Dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建访问令牌

    Args:
        data: 包含用户信息的字典，必须包含 sub(用户ID) 和 username
        expires_delta: 可选的过期时间增量

    Returns:
        JWT token字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: Dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建刷新令牌

    Args:
        data: 包含用户信息的字典
        expires_delta: 可选的过期时间增量

    Returns:
        JWT refresh token字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> bool:
    """
    验证令牌是否有效

    Args:
        token: JWT token字符串
        token_type: 令牌类型 ("access" 或 "refresh")

    Returns:
        是否有效
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_sub": False})
        if payload.get("type") != token_type:
            return False
        return True
    except PyJWTError:
        return False


def decode_token(token: str) -> Optional[Dict]:
    """
    解码令牌

    Args:
        token: JWT token字符串

    Returns:
        令牌payload字典，如果无效返回None
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_sub": False})
        return payload
    except PyJWTError:
        return None


def get_token_expiry(token: str) -> Optional[datetime]:
    """获取令牌过期时间"""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False}
        )
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        return None
    except PyJWTError:
        return None

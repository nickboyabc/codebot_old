"""
认证数据库管理
"""
import sqlite3
from pathlib import Path
from typing import Optional, Dict
from loguru import logger

from config import settings


class AuthDatabase:
    """认证数据库管理器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(settings.DATA_DIR / "auth.db")
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """连接数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"认证数据库连接成功：{self.db_path}")

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            logger.info("认证数据库连接已关闭")

    def init_tables(self):
        """初始化认证相关表"""
        cursor = self.conn.cursor()

        # 用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                created_by INTEGER,
                suspended_reason TEXT
            )
        """)

        # 审计日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 会话表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username
            ON users(username)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_username
            ON audit_logs(username)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_created
            ON audit_logs(created_at DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id
            ON sessions(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_refresh_token
            ON sessions(refresh_token)
        """)

        self.conn.commit()
        logger.info("认证数据库表初始化完成")

    def create_default_users(self):
        """创建默认用户（如果不存在）"""
        cursor = self.conn.cursor()

        # 检查是否已存在默认用户
        cursor.execute("SELECT COUNT(*) FROM users WHERE username IN ('admin', 'user1')")
        count = cursor.fetchone()[0]
        if count > 0:
            logger.info("默认用户已存在，跳过创建")
            return

        from passlib.context import CryptContext
        import os
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        # 从环境变量读取默认密码，默认为空（不创建默认用户）
        admin_username = os.environ.get("CODEBOT_ADMIN_USER", "admin").strip()
        admin_password = os.environ.get("CODEBOT_ADMIN_PASSWORD", "").strip()
        user1_username = os.environ.get("CODEBOT_USER1_USER", "user1").strip()
        user1_password = os.environ.get("CODEBOT_USER1_PASSWORD", "").strip()

        # 只有明确设置了密码才创建默认用户
        if admin_password:
            admin_hash = pwd_context.hash(admin_password)
            cursor.execute(
                """INSERT INTO users (username, password_hash, role, status)
                   VALUES (?, ?, ?, ?)""",
                (admin_username, admin_hash, "admin", "active")
            )
            logger.info(f"创建默认管理员用户：{admin_username}")

        if user1_password:
            user1_hash = pwd_context.hash(user1_password)
            cursor.execute(
                """INSERT INTO users (username, password_hash, role, status)
                   VALUES (?, ?, ?, ?)""",
                (user1_username, user1_hash, "user", "active")
            )
            logger.info(f"创建默认用户：{user1_username}")

        self.conn.commit()

    def get_user(self, username: str) -> Optional[Dict]:
        """根据用户名获取用户"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据用户ID获取用户"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "user",
        status: str = "pending",
        created_by: int = None
    ) -> int:
        """创建用户"""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO users (username, password_hash, role, status, created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (username, password_hash, role, status, created_by)
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_user_status(
        self,
        user_id: int,
        status: str,
        suspended_reason: str = None
    ):
        """更新用户状态"""
        cursor = self.conn.cursor()
        if suspended_reason is not None:
            cursor.execute(
                """UPDATE users SET status = ?, suspended_reason = ?,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (status, suspended_reason, user_id)
            )
        else:
            cursor.execute(
                """UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (status, user_id)
            )
        self.conn.commit()

    def update_last_login(self, user_id: int):
        """更新最后登录时间"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,)
        )
        self.conn.commit()

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.verify(plain_password, hashed_password)

    def password_hash(self, password: str) -> str:
        """密码哈希"""
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.hash(password)

    def list_users(self) -> list:
        """获取所有用户列表"""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT id, username, role, status, created_at, updated_at,
                      last_login, created_by, suspended_reason
               FROM users ORDER BY id"""
        )
        return [dict(row) for row in cursor.fetchall()]

    def delete_user(self, user_id: int):
        """删除用户"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()

    def log_audit(
        self,
        username: str,
        action: str,
        resource: str = None,
        details: str = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """记录审计日志"""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO audit_logs
               (username, action, resource, details, ip_address, user_agent)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, action, resource, details, ip_address, user_agent)
        )
        self.conn.commit()

    def get_audit_logs(
        self,
        username: str = None,
        action: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """获取审计日志"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if username:
            query += " AND username = ?"
            params.append(username)
        if action:
            query += " AND action = ?"
            params.append(action)
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_audit_logs_count(
        self,
        username: str = None,
        action: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> int:
        """获取审计日志总数"""
        cursor = self.conn.cursor()
        query = "SELECT COUNT(*) FROM audit_logs WHERE 1=1"
        params = []

        if username:
            query += " AND username = ?"
            params.append(username)
        if action:
            query += " AND action = ?"
            params.append(action)
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)

        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def get_user_stats(self, username: str = None) -> Dict:
        """获取用户统计信息"""
        cursor = self.conn.cursor()

        if username:
            # 指定用户的统计
            cursor.execute(
                """SELECT action, COUNT(*) as count
                   FROM audit_logs WHERE username = ?
                   GROUP BY action""",
                (username,)
            )
            actions = {row["action"]: row["count"] for row in cursor.fetchall()}

            cursor.execute(
                """SELECT COUNT(DISTINCT DATE(created_at)) as active_days
                   FROM audit_logs WHERE username = ?""",
                (username,)
            )
            active_days = cursor.fetchone()[0] or 0

            return {
                "actions": actions,
                "active_days": active_days,
                "total_actions": sum(actions.values())
            }
        else:
            # 全局统计
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
            active_users = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'")
            pending_users = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'suspended'")
            suspended_users = cursor.fetchone()[0] or 0

            cursor.execute(
                """SELECT action, COUNT(*) as count
                   FROM audit_logs GROUP BY action"""
            )
            actions = {row["action"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM audit_logs")
            total_logs = cursor.fetchone()[0] or 0

            return {
                "total_users": total_users,
                "active_users": active_users,
                "pending_users": pending_users,
                "suspended_users": suspended_users,
                "actions": actions,
                "total_logs": total_logs
            }

    # 会话管理
    def create_session(self, user_id: int, refresh_token: str, expires_at: str) -> int:
        """创建会话"""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO sessions (user_id, refresh_token, expires_at)
               VALUES (?, ?, ?)""",
            (user_id, refresh_token, expires_at)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_session_by_token(self, refresh_token: str) -> Optional[Dict]:
        """根据refresh token获取会话"""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM sessions
               WHERE refresh_token = ? AND revoked = 0 AND expires_at > datetime('now')""",
            (refresh_token,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def revoke_session(self, refresh_token: str):
        """撤销会话"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE sessions SET revoked = 1 WHERE refresh_token = ?",
            (refresh_token,)
        )
        self.conn.commit()

    def revoke_all_user_sessions(self, user_id: int):
        """撤销用户所有会话"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE sessions SET revoked = 1 WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()


# 全局认证数据库实例
auth_db = AuthDatabase()


def get_auth_db() -> AuthDatabase:
    """获取认证数据库实例"""
    global auth_db
    if auth_db.conn is None:
        auth_db.connect()
        auth_db.init_tables()
        auth_db.create_default_users()
    return auth_db

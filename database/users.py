"""用户数据访问和用户表结构迁移。"""

import json
import sqlite3
from typing import Any

from database.connection import utc_now
from werkzeug.security import generate_password_hash


USER_FIELDS = (
    "id",
    "username",
    "password_hash",
    "email",
    "nickname",
    "role",
    "status",
    "created_at",
    "updated_at",
    "session_version",
)


def migrate_users(database: sqlite3.Connection) -> None:
    """兼容已有 users 表，增加认证模块需要的字段，不删除已有数据。"""

    columns = {
        row["name"] for row in database.execute("PRAGMA table_info(users)")
    }
    migrations = {
        "password_hash": (
            "ALTER TABLE users ADD COLUMN password_hash "
            "TEXT NOT NULL DEFAULT ''"
        ),
        "username_key": (
            "ALTER TABLE users ADD COLUMN username_key "
            "TEXT NOT NULL DEFAULT ''"
        ),
        "email": "ALTER TABLE users ADD COLUMN email TEXT",
        "nickname": "ALTER TABLE users ADD COLUMN nickname TEXT NOT NULL DEFAULT ''",
        "role": "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'",
        "status": "ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
        "created_at": (
            "ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
        ),
        "updated_at": (
            "ALTER TABLE users ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
        ),
        "session_version": (
            "ALTER TABLE users ADD COLUMN session_version "
            "INTEGER NOT NULL DEFAULT 1"
        ),
    }
    for column, statement in migrations.items():
        if column not in columns:
            database.execute(statement)

    now = utc_now()
    database.execute(
        "UPDATE users SET username_key = lower(username) WHERE username_key = ''"
    )
    database.execute(
        "UPDATE users SET created_at = ? WHERE created_at = ''",
        (now,),
    )
    database.execute(
        "UPDATE users SET updated_at = ? WHERE updated_at = ''",
        (now,),
    )
    database.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username_key "
        "ON users(username_key)"
    )


def find_user_by_username(
    database: sqlite3.Connection,
    username: str,
) -> sqlite3.Row | None:
    """按用户名查询用户。"""

    return database.execute(
        "SELECT id, username, password_hash, email, nickname, role, status, "
        "created_at, updated_at, session_version FROM users "
        "WHERE username_key = ?",
        (username.strip().lower(),),
    ).fetchone()


def find_user_by_id(
    database: sqlite3.Connection,
    user_id: int,
) -> sqlite3.Row | None:
    """按用户编号查询用户。"""

    return database.execute(
        "SELECT id, username, password_hash, email, nickname, role, status, "
        "created_at, updated_at, session_version FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def create_user(
    database: sqlite3.Connection,
    username: str,
    password: str,
    email: str | None,
    nickname: str,
) -> sqlite3.Row:
    """创建用户，数据库只保存 Werkzeug 生成的密码哈希。"""

    password_hash = generate_password_hash(password)
    now = utc_now()
    cursor = database.execute(
        "INSERT INTO users "
        "(username, username_key, password_hash, email, nickname, role, status, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'user', 'active', ?, ?)",
        (username, username.lower(), password_hash, email, nickname, now, now),
    )
    user = find_user_by_id(database, cursor.lastrowid)
    if user is None:
        raise RuntimeError("用户创建后无法读取用户记录")
    return user


def update_profile(
    database: sqlite3.Connection,
    user_id: int,
    nickname: str,
    email: str | None,
) -> sqlite3.Row:
    """更新用户昵称和邮箱。"""

    now = utc_now()
    database.execute(
        "UPDATE users SET nickname = ?, email = ?, updated_at = ? WHERE id = ?",
        (nickname, email, now, user_id),
    )
    user = find_user_by_id(database, user_id)
    if user is None:
        raise RuntimeError("用户资料更新后无法读取用户记录")
    return user


def update_password(
    database: sqlite3.Connection,
    user_id: int,
    password_hash: str,
) -> int:
    """更新密码并递增会话版本，使旧会话失效。"""

    now = utc_now()
    cursor = database.execute(
        "UPDATE users SET password_hash = ?, session_version = "
        "session_version + 1, updated_at = ? WHERE id = ?",
        (password_hash, now, user_id),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("用户密码更新失败")
    user = find_user_by_id(database, user_id)
    if user is None:
        raise RuntimeError("密码更新后无法读取用户记录")
    return int(user["session_version"])


def public_user(user: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """转换为不包含密码哈希的公开用户信息。"""

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "nickname": user["nickname"],
        "role": user["role"],
        "status": user["status"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
    }


def list_users(
    database: sqlite3.Connection,
    search: str,
    limit: int,
    offset: int,
) -> tuple[list[sqlite3.Row], int]:
    """分页查询用户，查询结果不包含密码哈希。"""

    escaped = (
        search.lower()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    pattern = f"%{escaped}%"
    rows = database.execute(
        "SELECT id, username, email, nickname, role, status, created_at "
        "FROM users WHERE username_key LIKE ? ESCAPE '\\' "
        "ORDER BY id LIMIT ? OFFSET ?",
        (pattern, limit, offset),
    ).fetchall()
    total = database.execute(
        "SELECT COUNT(*) FROM users WHERE username_key LIKE ? ESCAPE '\\'",
        (pattern,),
    ).fetchone()[0]
    return rows, int(total)


def public_admin_user(user: sqlite3.Row) -> dict[str, Any]:
    """转换为管理员接口可见的用户信息。"""

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "nickname": user["nickname"],
        "role": user["role"],
        "status": user["status"],
        "created_at": user["created_at"],
    }


def update_user_status(
    database: sqlite3.Connection,
    target_user_id: int,
    status: str,
    actor_user_id: int,
) -> sqlite3.Row | None:
    """更新普通用户状态并写入审计日志。"""

    now = utc_now()
    cursor = database.execute(
        "UPDATE users SET status = ?, updated_at = ? "
        "WHERE id = ? AND role = 'user'",
        (status, now, target_user_id),
    )
    if cursor.rowcount != 1:
        return None
    database.execute(
        "INSERT INTO audit_logs "
        "(actor_user_id, action, target_user_id, details, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            actor_user_id,
            "user_status_changed",
            target_user_id,
            json.dumps({"status": status}, ensure_ascii=False),
            now,
        ),
    )
    return find_user_by_id(database, target_user_id)


def add_audit_log(
    database: sqlite3.Connection,
    actor_user_id: int | None,
    action: str,
    target_user_id: int | None,
    details: dict[str, Any] | None = None,
) -> None:
    """写入不包含密码和密钥的审计记录。"""

    database.execute(
        "INSERT INTO audit_logs "
        "(actor_user_id, action, target_user_id, details, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            actor_user_id,
            action,
            target_user_id,
            json.dumps(details or {}, ensure_ascii=False),
            utc_now(),
        ),
    )

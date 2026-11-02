"""SQLite 连接和初始化管理。"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from flask import Flask, current_app, g


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    """获取当前 Flask 应用上下文中的数据库连接。"""

    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        g.db = connection
    return g.db


def close_db(error: BaseException | None = None) -> None:
    """在请求或应用上下文结束时关闭数据库连接。"""

    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


@contextmanager
def db_transaction() -> Iterator[sqlite3.Connection]:
    """统一管理一次业务操作的提交和回滚边界。"""

    database = get_db()
    try:
        yield database
        database.commit()
    except Exception:
        database.rollback()
        raise


def init_db(app: Flask) -> None:
    """执行数据库初始化脚本。"""

    if app.extensions.get("travelmate_database_initialized"):
        return
    from database.users import migrate_users

    schema_path = Path(__file__).with_name("schema.sql")
    schema = schema_path.read_text(encoding="utf-8")
    with app.app_context():
        with db_transaction() as database:
            database.executescript(schema)
            migrate_users(database)
    app.extensions["travelmate_database_initialized"] = True

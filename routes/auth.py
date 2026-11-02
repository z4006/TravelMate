"""用户注册、登录、资料和密码管理接口。"""

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, g, session
from werkzeug.security import check_password_hash, generate_password_hash

from database.connection import db_transaction, get_db, utc_now
from database.users import (
    add_audit_log,
    create_user,
    find_user_by_id,
    find_user_by_username,
    public_user,
    update_password,
    update_profile,
)
from utils.decorators import csrf_protected, login_required
from utils.responses import api_response, request_data
from utils.validators import (
    normalize_username,
    validate_email,
    validate_nickname,
    validate_password,
    validate_username,
)


auth_bp = Blueprint("auth", __name__)
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_FAILURE_LIMIT = 5


def _client_ip() -> str:
    from flask import request

    return request.remote_addr or "unknown"


def _too_many_login_attempts(database: sqlite3.Connection, username: str) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=LOGIN_WINDOW_SECONDS)).isoformat()
    row = database.execute(
        "SELECT COUNT(*) FROM login_attempts "
        "WHERE username_key = ? AND ip_address = ? "
        "AND failed_at >= ?",
        (normalize_username(username), _client_ip(), cutoff),
    ).fetchone()
    return bool(row[0] >= LOGIN_FAILURE_LIMIT)


def _record_login_failure(database: sqlite3.Connection, username: str) -> None:
    database.execute(
        "INSERT INTO login_attempts (username_key, ip_address, failed_at) "
        "VALUES (?, ?, ?)",
        (normalize_username(username), _client_ip(), utc_now()),
    )


@auth_bp.get("/api/csrf-token")
def csrf_token():
    """为前端获取写操作所需的 CSRF token。"""

    token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return api_response(True, "操作成功", {"csrf_token": token})


@auth_bp.post("/api/register")
@csrf_protected
def register():
    payload = request_data()
    if payload is None:
        return api_response(False, "请求体必须是 JSON", None, 400)
    username = payload.get("username")
    password = payload.get("password")
    email = payload.get("email")
    nickname = payload.get("nickname") or username
    username_error = validate_username(username)
    password_error = validate_password(password)
    email_error = validate_email(email)
    nickname_error = validate_nickname(nickname)
    if username_error or password_error or email_error or nickname_error:
        return api_response(
            False,
            username_error or password_error or email_error or nickname_error,
            None,
            400,
        )
    username = normalize_username(username)
    nickname = nickname.strip()
    database = get_db()
    if find_user_by_username(database, username) is not None:
        return api_response(False, "用户名已存在", None, 409)
    try:
        with db_transaction():
            user = create_user(database, username, password, email or None, nickname)
            add_audit_log(database, None, "user_registered", user["id"])
    except sqlite3.IntegrityError:
        return api_response(False, "用户名已存在", None, 409)
    return api_response(True, "注册成功", public_user(user), 201)


@auth_bp.post("/api/login")
@csrf_protected
def login():
    payload = request_data()
    if payload is None:
        return api_response(False, "请求体必须是 JSON", None, 400)
    username = payload.get("username")
    password = payload.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return api_response(False, "用户名和密码不能为空", None, 400)
    database = get_db()
    if _too_many_login_attempts(database, username):
        return api_response(False, "登录尝试次数过多，请稍后再试", None, 429)
    user = find_user_by_username(database, username)
    if (
        user is None
        or not check_password_hash(user["password_hash"], password)
        or user["status"] != "active"
    ):
        with db_transaction():
            _record_login_failure(database, username)
            add_audit_log(database, None, "login_failed", user["id"] if user else None)
        return api_response(False, "用户名或密码错误", None, 401)
    with db_transaction():
        database.execute(
            "DELETE FROM login_attempts WHERE username_key = ? AND ip_address = ?",
            (normalize_username(username), _client_ip()),
        )
        add_audit_log(database, user["id"], "login_succeeded", user["id"])
    session.clear()
    session["csrf_token"] = secrets.token_urlsafe(32)
    session["user_id"] = user["id"]
    session["session_version"] = user["session_version"]
    session.permanent = True
    return api_response(True, "登录成功", public_user(user))


@auth_bp.post("/api/logout")
@csrf_protected
def logout():
    user_id = session.get("user_id")
    with db_transaction():
        if isinstance(user_id, int):
            add_audit_log(get_db(), user_id, "logout", user_id)
    session.clear()
    return api_response(True, "退出登录成功", None)


@auth_bp.get("/api/user/info")
@login_required
def user_info():
    return api_response(True, "操作成功", public_user(g.current_user))


@auth_bp.put("/api/user/profile")
@csrf_protected
@login_required
def profile():
    payload = request_data()
    if payload is None:
        return api_response(False, "请求体必须是 JSON", None, 400)
    if "role" in payload or "status" in payload:
        return api_response(False, "不允许修改角色或账户状态", None, 400)
    nickname = payload.get("nickname", g.current_user["nickname"])
    email = payload.get("email", g.current_user["email"])
    nickname_error = validate_nickname(nickname)
    email_error = validate_email(email)
    if nickname_error or email_error:
        return api_response(False, nickname_error or email_error, None, 400)
    with db_transaction():
        user = update_profile(
            get_db(),
            g.current_user["id"],
            nickname.strip(),
            email or None,
        )
        add_audit_log(get_db(), g.current_user["id"], "profile_updated", user["id"])
    return api_response(True, "资料修改成功", public_user(user))


@auth_bp.put("/api/user/password")
@csrf_protected
@login_required
def password():
    payload = request_data()
    if payload is None:
        return api_response(False, "请求体必须是 JSON", None, 400)
    old_password = payload.get("old_password")
    new_password = payload.get("new_password")
    if not isinstance(old_password, str) or not isinstance(new_password, str):
        return api_response(False, "必须提供原密码和新密码", None, 400)
    if not check_password_hash(g.current_user["password_hash"], old_password):
        return api_response(False, "原密码错误", None, 401)
    password_error = validate_password(new_password)
    if password_error:
        return api_response(False, password_error, None, 400)
    with db_transaction():
        version = update_password(
            get_db(),
            g.current_user["id"],
            generate_password_hash(new_password),
        )
        add_audit_log(get_db(), g.current_user["id"], "password_changed", g.current_user["id"])
    session["session_version"] = version
    return api_response(True, "密码修改成功", None)

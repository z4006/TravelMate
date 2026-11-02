"""登录、角色和 CSRF 守卫。"""

import secrets
from functools import wraps
from typing import Callable

from flask import g, request, session

from database.connection import get_db
from database.users import find_user_by_id
from utils.responses import api_response, request_data


def csrf_protected(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = session.get("csrf_token")
        supplied = request.headers.get("X-CSRF-Token") or (
            request_data() or {}
        ).get("csrf_token")
        if not expected or not supplied or not secrets.compare_digest(
            str(expected), str(supplied)
        ):
            return api_response(False, "CSRF 校验失败", None, 403)
        return view(*args, **kwargs)

    return wrapped


def login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        session_version = session.get("session_version")
        if not isinstance(user_id, int) or not isinstance(session_version, int):
            return api_response(False, "请先登录", None, 401)
        user = find_user_by_id(get_db(), user_id)
        if (
            user is None
            or user["status"] != "active"
            or user["session_version"] != session_version
        ):
            session.clear()
            return api_response(False, "登录状态已失效，请重新登录", None, 401)
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles: str):
    def decorator(view: Callable):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.current_user["role"] not in roles:
                return api_response(False, "没有访问权限", None, 403)
            return view(*args, **kwargs)

        return wrapped

    return decorator

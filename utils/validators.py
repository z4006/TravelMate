"""认证和用户输入校验。"""

import re
from typing import Any


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: Any) -> str | None:
    if not isinstance(username, str) or not USERNAME_PATTERN.fullmatch(username):
        return "用户名必须为 3-32 位字母、数字或下划线"
    return None


def validate_password(password: Any) -> str | None:
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        return "密码长度必须为 8-128 位"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "密码必须同时包含字母和数字"
    return None


def validate_email(email: Any) -> str | None:
    if email is None or email == "":
        return None
    if not isinstance(email, str) or len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return "邮箱格式不正确"
    return None


def validate_nickname(nickname: Any) -> str | None:
    if not isinstance(nickname, str) or not 1 <= len(nickname.strip()) <= 64:
        return "昵称长度必须为 1-64 位"
    return None

"""管理员用户管理接口。"""

from flask import Blueprint, g, request

from database.connection import db_transaction, get_db
from database.users import (
    add_audit_log,
    find_user_by_id,
    list_users,
    public_admin_user,
    update_user_status,
)
from utils.decorators import csrf_protected, role_required
from utils.responses import api_response, request_data


admin_bp = Blueprint("admin", __name__)


admin_required = role_required("admin")


def parse_user_id(raw_user_id: str) -> int | None:
    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        return None
    return user_id if user_id > 0 else None


@admin_bp.get("/api/admin/users")
@admin_required
def admin_users():
    """分页查询用户列表，支持按用户名搜索。"""

    raw_page = request.args.get("page", "1")
    raw_page_size = request.args.get("page_size", "20")
    search = request.args.get("search", "").strip()
    try:
        page = int(raw_page)
        page_size = int(raw_page_size)
    except ValueError:
        return api_response(False, "分页参数必须是整数", None, 400)
    if page < 1 or not 1 <= page_size <= 100:
        return api_response(False, "分页参数不合法", None, 400)
    if len(search) > 100:
        return api_response(False, "搜索关键词过长", None, 400)
    rows, total = list_users(
        get_db(),
        search,
        page_size,
        (page - 1) * page_size,
    )
    return api_response(
        True,
        "操作成功",
        {
            "items": [public_admin_user(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@admin_bp.get("/api/admin/users/<user_id>")
@admin_required
def admin_user_detail(user_id: str):
    """查看指定用户的基本资料。"""

    parsed_user_id = parse_user_id(user_id)
    if parsed_user_id is None:
        return api_response(False, "用户 ID 不合法", None, 400)
    user = find_user_by_id(get_db(), parsed_user_id)
    if user is None:
        return api_response(False, "用户不存在", None, 404)
    with db_transaction():
        add_audit_log(
            get_db(),
            g.current_user["id"],
            "admin_viewed_user",
            parsed_user_id,
        )
    return api_response(True, "操作成功", public_admin_user(user))


@admin_bp.patch("/api/admin/users/<user_id>/status")
@csrf_protected
@admin_required
def admin_user_status(user_id: str):
    """启用或禁用普通用户，不允许修改管理员状态。"""

    parsed_user_id = parse_user_id(user_id)
    if parsed_user_id is None:
        return api_response(False, "用户 ID 不合法", None, 400)
    payload = request_data()
    status = payload.get("status") if isinstance(payload, dict) else None
    if status not in {"active", "disabled"}:
        return api_response(False, "账户状态必须是 active 或 disabled", None, 400)
    target = find_user_by_id(get_db(), parsed_user_id)
    if target is None:
        return api_response(False, "用户不存在", None, 404)
    if target["role"] != "user":
        return api_response(False, "不能通过此接口修改管理员状态", None, 403)
    with db_transaction():
        updated = update_user_status(
            get_db(),
            parsed_user_id,
            status,
            g.current_user["id"],
        )
    if updated is None:
        return api_response(False, "目标用户状态已变化，请刷新后重试", None, 409)
    return api_response(True, "用户状态更新成功", public_admin_user(updated))

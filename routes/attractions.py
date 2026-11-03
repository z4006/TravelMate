"""景点查询 API。"""

import sqlite3
from typing import Any

from flask import Blueprint, request

from database.attractions import (
    get_attraction_by_id,
    list_attractions,
    list_categories,
)
from database.connection import get_db
from utils.responses import api_response


attractions_bp = Blueprint("attractions", __name__)


def _public_attraction(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "category": {
            "id": row["category_id"],
            "name": row["category_name"],
            "slug": row["category_slug"],
        },
        "city": row["city"],
        "address": row["address"],
        "description": row["description"],
        "ticket_price_cents": row["ticket_price_cents"],
        "opening_hours": row["opening_hours"],
        "image_url": row["image_url"],
        "source": row["source"],
        "source_id": row["source_id"],
        "source_url": row["source_url"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@attractions_bp.get("/api/attractions")
def attractions():
    """分页查询公开景点，可按分类、城市和关键词筛选。"""

    try:
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "20"))
    except ValueError:
        return api_response(False, "分页参数必须是整数", None, 400)
    if page < 1 or not 1 <= page_size <= 100:
        return api_response(False, "分页参数不合法", None, 400)

    category = request.args.get("category", "").strip()
    city = request.args.get("city", "").strip()
    keyword = request.args.get("q", "").strip()
    if any(len(value) > 100 for value in (category, city, keyword)):
        return api_response(False, "筛选参数不能超过 100 个字符", None, 400)

    rows, total = list_attractions(
        get_db(),
        category or None,
        city or None,
        keyword or None,
        page_size,
        (page - 1) * page_size,
    )
    return api_response(
        True,
        "操作成功",
        {
            "items": [_public_attraction(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@attractions_bp.get("/api/attractions/categories")
def attraction_categories():
    """查询景点分类。"""

    categories = [
        {"id": row["id"], "name": row["name"], "slug": row["slug"]}
        for row in list_categories(get_db())
    ]
    return api_response(True, "操作成功", {"items": categories})


@attractions_bp.get("/api/attractions/<attraction_id>")
def attraction_detail(attraction_id: str):
    """查询单个公开景点。"""

    try:
        parsed_id = int(attraction_id)
    except ValueError:
        return api_response(False, "景点 ID 不合法", None, 400)
    if parsed_id < 1:
        return api_response(False, "景点 ID 不合法", None, 400)

    row = get_attraction_by_id(get_db(), parsed_id)
    if row is None:
        return api_response(False, "景点不存在", None, 404)
    return api_response(True, "操作成功", _public_attraction(row))

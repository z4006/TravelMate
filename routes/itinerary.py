"""收藏和旅游行程 API。"""

import sqlite3
from datetime import date
from typing import Any

from flask import Blueprint, g

from database.connection import db_transaction, get_db
from database.itineraries import (
    attraction_exists,
    create_favorite,
    create_itinerary,
    delete_favorite,
    delete_itinerary,
    ensure_itinerary_tables,
    get_itinerary,
    list_favorites,
    list_itineraries,
    update_itinerary,
)
from utils.decorators import csrf_protected, login_required
from utils.responses import api_response, request_data


itinerary_bp = Blueprint("itinerary", __name__)


def _ensure_tables() -> None:
    ensure_itinerary_tables()


def _date(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _itinerary_payload(payload: dict[str, Any]):
    title = payload.get("title")
    attractions = payload.get("attractions", [])
    notes = payload.get("notes")
    if (
        not isinstance(title, str)
        or not 1 <= len(title.strip()) <= 120
        or (notes is not None and not isinstance(notes, str))
        or not isinstance(attractions, list)
        or any(not isinstance(item, dict) for item in attractions)
    ):
        return None
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    if not _date(start_date) or not _date(end_date):
        return None
    if start_date and end_date and end_date < start_date:
        return None
    attraction_ids = set()
    for index, item in enumerate(attractions):
        item.setdefault("sort_order", index)
        if (
            not isinstance(item.get("attraction_id"), int)
            or isinstance(item.get("attraction_id"), bool)
            or item["attraction_id"] in attraction_ids
            or not isinstance(item.get("sort_order"), int)
            or isinstance(item.get("sort_order"), bool)
            or not _date(item.get("visit_date"))
            or (
                item.get("notes") is not None
                and not isinstance(item.get("notes"), str)
            )
        ):
            return None
        attraction_ids.add(item["attraction_id"])
    return (
        title.strip(),
        start_date,
        end_date,
        payload.get("notes"),
        attractions,
    )


@itinerary_bp.post("/api/favorites")
@csrf_protected
@login_required
def add_favorite():
    _ensure_tables()
    payload = request_data()
    attraction_id = payload.get("attraction_id") if payload else None
    database = get_db()
    if not isinstance(attraction_id, int) or isinstance(attraction_id, bool):
        return api_response(False, "景点编号无效", None, 400)
    if not attraction_exists(database, attraction_id):
        return api_response(False, "景点不存在", None, 404)
    try:
        with db_transaction():
            favorite = create_favorite(database, g.current_user["id"], attraction_id)
    except sqlite3.IntegrityError:
        return api_response(False, "该景点已收藏", None, 409)
    return api_response(True, "收藏成功", favorite, 201)


@itinerary_bp.delete("/api/favorites/<int:attraction_id>")
@csrf_protected
@login_required
def remove_favorite(attraction_id: int):
    _ensure_tables()
    with db_transaction():
        removed = delete_favorite(get_db(), g.current_user["id"], attraction_id)
    if not removed:
        return api_response(False, "收藏不存在", None, 404)
    return api_response(True, "取消收藏成功", None)


@itinerary_bp.get("/api/favorites")
@login_required
def favorites():
    _ensure_tables()
    return api_response(True, "操作成功", list_favorites(get_db(), g.current_user["id"]))


@itinerary_bp.post("/api/itineraries")
@csrf_protected
@login_required
def add_itinerary():
    _ensure_tables()
    payload = request_data()
    values = _itinerary_payload(payload) if payload else None
    database = get_db()
    if values is None:
        return api_response(False, "行程参数无效", None, 400)
    title, start_date, end_date, notes, attractions = values
    if not all(attraction_exists(database, item["attraction_id"]) for item in attractions):
        return api_response(False, "景点不存在", None, 404)
    with db_transaction():
        itinerary = create_itinerary(
            database, g.current_user["id"], title, start_date, end_date, notes, attractions
        )
    return api_response(True, "行程创建成功", itinerary, 201)


@itinerary_bp.get("/api/itineraries")
@login_required
def itineraries():
    _ensure_tables()
    return api_response(True, "操作成功", list_itineraries(get_db(), g.current_user["id"]))


@itinerary_bp.get("/api/itineraries/<int:itinerary_id>")
@login_required
def itinerary_detail(itinerary_id: int):
    _ensure_tables()
    itinerary = get_itinerary(get_db(), g.current_user["id"], itinerary_id)
    if itinerary is None:
        return api_response(False, "行程不存在", None, 404)
    return api_response(True, "操作成功", itinerary)


@itinerary_bp.put("/api/itineraries/<int:itinerary_id>")
@csrf_protected
@login_required
def edit_itinerary(itinerary_id: int):
    _ensure_tables()
    payload = request_data()
    values = _itinerary_payload(payload) if payload else None
    database = get_db()
    if values is None:
        return api_response(False, "行程参数无效", None, 400)
    title, start_date, end_date, notes, attractions = values
    if not all(attraction_exists(database, item["attraction_id"]) for item in attractions):
        return api_response(False, "景点不存在", None, 404)
    with db_transaction():
        itinerary = update_itinerary(
            database, g.current_user["id"], itinerary_id,
            title, start_date, end_date, notes, attractions,
        )
    if itinerary is None:
        return api_response(False, "行程不存在", None, 404)
    return api_response(True, "行程修改成功", itinerary)


@itinerary_bp.delete("/api/itineraries/<int:itinerary_id>")
@csrf_protected
@login_required
def remove_itinerary(itinerary_id: int):
    _ensure_tables()
    with db_transaction():
        removed = delete_itinerary(get_db(), g.current_user["id"], itinerary_id)
    if not removed:
        return api_response(False, "行程不存在", None, 404)
    return api_response(True, "行程删除成功", None)


@itinerary_bp.get("/api/itineraries/recommendations")
@login_required
def recommendations():
    _ensure_tables()
    database = get_db()
    rows = database.execute(
        "SELECT attraction_id, COUNT(*) AS favorite_count "
        "FROM favorites GROUP BY attraction_id ORDER BY favorite_count DESC, attraction_id "
        "LIMIT 10"
    ).fetchall()
    return api_response(True, "操作成功", [dict(row) for row in rows])

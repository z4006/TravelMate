"""AI 助手接口（成员 D）：行程规划与旅行问答。"""

from flask import Blueprint, g

from database.attractions import list_attractions
from database.connection import db_transaction, get_db
from database.itineraries import create_itinerary
from services.agent import (
    MAX_MESSAGE_LENGTH,
    chat_reply,
    is_configured,
    pick_candidates,
    plan_itinerary,
    to_itinerary_payload,
    write_caption,
)
from utils.decorators import csrf_protected, login_required
from utils.responses import api_response, request_data

agent_bp = Blueprint("agent", __name__)



def _load_candidates(city: str | None, message: str = "") -> list[dict]:
    """读取景点后按问题筛选，避免只把前几十条塞给模型。"""

    rows, _total = list_attractions(get_db(), None, city, None, 500, 0)
    records = [dict(row) for row in rows]
    return pick_candidates(records, message, limit=30)


@agent_bp.get("/api/agent/status")
def agent_status():
    """返回 AI 助手是否已配置模型，供前端提示。"""

    return api_response(True, "操作成功", {"configured": is_configured()})


@agent_bp.post("/api/agent/chat")
@csrf_protected
@login_required
def agent_chat():
    """旅行问答，支持前端回传多轮历史。"""

    payload = request_data()
    if payload is None:
        return api_response(False, "请求体必须是 JSON", None, 400)

    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        return api_response(False, "请输入你想问的问题", None, 400)
    message = message.strip()
    if len(message) > MAX_MESSAGE_LENGTH:
        return api_response(False, "问题描述过长，请精简后再试", None, 400)

    raw_history = payload.get("history", [])
    if not isinstance(raw_history, list):
        return api_response(False, "history 必须是数组", None, 400)
    history = [item for item in raw_history if isinstance(item, dict)][:12]

    candidates = _load_candidates(None, message)
    reply, source = chat_reply(message, history, candidates)
    return api_response(
        True,
        "操作成功",
        {"reply": reply, "source": source, "model_configured": is_configured()},
    )


@agent_bp.post("/api/agent/copywrite")
@csrf_protected
@login_required
def agent_copywrite():
    """根据已生成的行程写一条分享文案（小红书风格）。"""

    payload = request_data()
    if payload is None:
        return api_response(False, "请求体必须是 JSON", None, 400)

    plan = payload.get("plan")
    if not isinstance(plan, dict):
        return api_response(False, "缺少行程数据", None, 400)

    raw_days = plan.get("days")
    if not isinstance(raw_days, list) or not raw_days:
        return api_response(False, "行程里还没有安排景点", None, 400)

    days = []
    for index, raw_day in enumerate(raw_days[:7], start=1):
        if not isinstance(raw_day, dict):
            continue
        raw_items = raw_day.get("items")
        if not isinstance(raw_items, list):
            continue
        items = [
            {"name": str(item.get("name"))[:40]}
            for item in raw_items[:5]
            if isinstance(item, dict) and item.get("name")
        ]
        if items:
            days.append({"day": index, "items": items})

    if not days:
        return api_response(False, "行程里还没有可用的景点", None, 400)

    title = plan.get("title")
    city = payload.get("city")
    city = city.strip() if isinstance(city, str) and city.strip() else None

    text, source = write_caption(
        {"title": title if isinstance(title, str) else "", "days": days},
        city,
    )
    return api_response(
        True,
        "文案生成成功",
        {"text": text, "source": source},
    )


@agent_bp.post("/api/agent/plan")
@csrf_protected
@login_required
def agent_plan():
    """根据自然语言需求生成行程，可选直接保存。"""

    payload = request_data()
    if payload is None:
        return api_response(False, "请求体必须是 JSON", None, 400)

    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        return api_response(False, "请描述你的行程需求", None, 400)
    message = message.strip()
    if len(message) > MAX_MESSAGE_LENGTH:
        return api_response(False, "需求描述过长，请精简后再试", None, 400)

    days = payload.get("days", 3)
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 7:
        return api_response(False, "天数必须是 1-7 之间的整数", None, 400)

    city = payload.get("city")
    if city is not None and not isinstance(city, str):
        return api_response(False, "城市参数不合法", None, 400)
    city = (city or "").strip() or None

    start_date = payload.get("start_date")
    if start_date is not None and not isinstance(start_date, str):
        return api_response(False, "开始日期格式不正确", None, 400)
    if start_date == "":
        start_date = None

    save = payload.get("save", False)
    if not isinstance(save, bool):
        return api_response(False, "save 必须是布尔值", None, 400)



    candidates = _load_candidates(city, message)
    if not candidates:
        return api_response(False, "景点库暂时没有可用数据，请先导入景点", None, 404)

    plan, source = plan_itinerary(message, candidates, days)
    itinerary_payload = to_itinerary_payload(plan, start_date)

    saved = None
    if save:
        if not itinerary_payload["attractions"]:
            return api_response(False, "行程中没有可用景点，无法保存", None, 400)
        with db_transaction():
            saved = create_itinerary(
                get_db(),
                g.current_user["id"],
                itinerary_payload["title"][:120],
                itinerary_payload["start_date"],
                itinerary_payload["end_date"],
                itinerary_payload["notes"],
                itinerary_payload["attractions"],
            )

    return api_response(
        True,
        "行程生成成功",
        {
            "source": source,
            "model_configured": is_configured(),
            "plan": plan,
            "itinerary_payload": itinerary_payload,
            "saved": saved,
        },
    )

"""AI 助手接口（成员 D）：行程规划与旅行问答。"""

import time

from flask import Blueprint, g, request, session

from database.attractions import list_attractions
from database.connection import db_transaction, get_db
from database.itineraries import create_itinerary
from database.users import find_user_by_id
from services.agent import (
    MAX_MESSAGE_LENGTH,
    chat_reply,
    is_configured,
    pick_candidates,
    plan_itinerary,
    to_itinerary_payload,
)
from utils.decorators import csrf_protected
from utils.responses import api_response, request_data

agent_bp = Blueprint("agent", __name__)

# 游客（未登录）调用限制：默认每小时 30 次，避免共用密钥被刷
ANON_LIMIT = 30
ANON_WINDOW_SECONDS = 3600
_anon_hits: dict[str, list[float]] = {}


def _current_user():
    """可选登录：有有效会话就返回用户，否则返回 None。"""

    user = getattr(g, "current_user", None)
    if user is not None:
        return user
    user_id = session.get("user_id")
    version = session.get("session_version")
    if not isinstance(user_id, int) or not isinstance(version, int):
        return None
    row = find_user_by_id(get_db(), user_id)
    if row is None or row["status"] != "active" or row["session_version"] != version:
        return None
    g.current_user = row
    return row


def _anon_limited() -> bool:
    """对未登录访客做内存级限流，登录用户不受影响。"""

    ip = request.remote_addr or "unknown"
    now = time.time()
    hits = [moment for moment in _anon_hits.get(ip, []) if now - moment < ANON_WINDOW_SECONDS]
    if len(hits) >= ANON_LIMIT:
        _anon_hits[ip] = hits
        return True
    hits.append(now)
    _anon_hits[ip] = hits
    return False


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

    if _current_user() is None and _anon_limited():
        return api_response(False, "游客体验次数已用完，登录后可继续使用", None, 429)

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


@agent_bp.post("/api/agent/plan")
@csrf_protected
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

    user = _current_user()
    if save and user is None:
        return api_response(False, "保存行程需要先登录", None, 401)
    if user is None and _anon_limited():
        return api_response(False, "游客体验次数已用完，登录后可继续使用", None, 429)

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
                user["id"],
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

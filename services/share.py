"""行程分享文案生成（任务 D）。

复用 services/agent.py 的 ask_model（火山引擎 Ark，OpenAI 兼容），
未配置密钥或网络失败时降级为规则版模板，接口永远返回 200 而不是 500。
"""

from __future__ import annotations

from typing import Any

from services.agent import ask_model

MAX_TITLE_LENGTH = 60
MAX_COPY_LENGTH = 320

SHARE_SYSTEM_PROMPT = (
    "你是 TravelMate 的旅行文案写手。根据用户提供的行程信息，写一段可以发到"
    "小红书 / 朋友圈的分享文案。要求："
    "1) 第一行是吸引人的标题，带 1-2 个 emoji，不超过 20 字；"
    "2) 正文 2-4 句，口语化、有画面感，可以自然带入景点名和天数；"
    "3) 结尾加 3-5 个话题标签，用 # 开头；"
    "4) 不要出现「AI」「模型」「助手」等字样，不要编造行程里没有的景点；"
    "5) 直接输出文案正文，不要任何解释、不要使用 Markdown 代码块。"
)


def _cities(attractions: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for item in attractions:
        city = (item.get("city") or "").strip()
        if city:
            name = city[:-1] if city.endswith("市") and len(city) > 1 else city
            if name not in seen:
                seen.append(name)
    return seen


def _days(itinerary: dict[str, Any]) -> int:
    start = itinerary.get("start_date")
    end = itinerary.get("end_date")
    if not start or not end:
        return 0
    from datetime import date

    try:
        return max((date.fromisoformat(end) - date.fromisoformat(start)).days + 1, 1)
    except ValueError:
        return 0


def _summary_text(itinerary: dict[str, Any]) -> str:
    attractions = itinerary.get("attractions") or []
    cities = _cities(attractions)
    names = [
        item.get("name") or ("景点 #" + str(item.get("attraction_id")))
        for item in attractions
    ]
    parts: list[str] = []
    title = (itinerary.get("title") or "我的旅行").strip()
    days = _days(itinerary)
    if cities:
        parts.append("目的地：" + "、".join(cities[:6]))
    if days:
        parts.append("行程天数：" + str(days) + " 天")
    if names:
        parts.append("打卡景点：" + "、".join(names[:10]))
    if itinerary.get("notes"):
        parts.append("备注：" + str(itinerary["notes"])[:120])
    return title + "\n" + "\n".join(parts)


def fallback_copy(itinerary: dict[str, Any]) -> str:
    """无模型时的模板文案，保证功能可用。"""

    attractions = itinerary.get("attractions") or []
    cities = _cities(attractions)
    names = [
        item.get("name") or ("景点 #" + str(item.get("attraction_id")))
        for item in attractions
    ]
    days = _days(itinerary)
    title = (itinerary.get("title") or "我的旅行").strip()
    head = "✈️ " + (("、".join(cities[:3]) + " " + str(days) + " 日游")
                    if cities and days
                    else title)
    lines = [head]
    if names:
        lines.append("这一趟走过了 " + "、".join(names[:6]) + "，每一站都值得纪念。")
    else:
        lines.append("行程已经排好，就等出发了，每一站都值得纪念。")
    if cities:
        lines.append("在" + "、".join(cities[:3]) + "的风里，把日子过成了想要的样子。")
    tags = ["#旅行日记", "#TravelMate"]
    for city in cities[:2]:
        tags.append("#" + city)
    if days:
        tags.append("#" + str(days) + "日游")
    lines.append(" ".join(tags))
    return "\n".join(lines)[:MAX_COPY_LENGTH]


def build_share_copy(itinerary: dict[str, Any]) -> tuple[str, str]:
    """返回 (文案, 来源)，来源为 model 或 rule。"""

    brief = _summary_text(itinerary)
    content = ask_model(
        [
            {"role": "system", "content": SHARE_SYSTEM_PROMPT},
            {"role": "user", "content": brief[:MAX_TITLE_LENGTH * 20]},
        ],
        temperature=0.9,
    )
    if content and content.strip():
        text = content.strip().strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
        if len(text) > MAX_COPY_LENGTH:
            text = text[:MAX_COPY_LENGTH]
        if text:
            return text, "model"
    return fallback_copy(itinerary), "rule"

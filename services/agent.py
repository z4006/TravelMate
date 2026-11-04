"""AI 助手服务（成员 D）：行程规划 + 聊天。

接入的是火山引擎方舟（Ark）的 OpenAI 兼容接口，默认模型为 DeepSeek 系列。
实现约束：
1. 不引入第三方依赖，只用标准库 urllib；
2. 密钥从 instance/agent.env 或环境变量读取，绝不硬编码、不写日志、不进 Git；
3. 未配置密钥、网络失败或返回格式异常时自动降级，接口永远返回 200 而不是 500。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
REQUEST_TIMEOUT = 30
MAX_MESSAGE_LENGTH = 500
MAX_HISTORY_ITEMS = 12
MAX_DAYS = 7
MAX_CANDIDATES = 40

ENV_FILE = Path(__file__).resolve().parents[1] / "instance" / "agent.env"

PLAN_SYSTEM_PROMPT = (
    "你是 TravelMate 的行程规划助手。根据用户需求，从给定景点列表中挑选景点并安排日程。"
    "硬性规则："
    "1) 只能使用景点列表中出现的 attraction_id，绝对不要编造不存在的编号；"
    "2) 同一天安排的景点不要超过 3 个；"
    "3) 只输出 JSON，不要输出任何解释文字。"
    "输出格式："
    '{"title": "行程标题", "summary": "一句话说明", '
    '"days": [{"day": 1, "items": [{"attraction_id": 1, "note": "上午游览，约 2 小时"}]}]}'
)

CHAT_SYSTEM_PROMPT = (
    "你是 TravelMate 的旅行助手，说话像本地朋友：轻松、有点幽默、不说官腔。"
    "回答控制在 120 字以内，先给结论，再给一两条能马上行动的建议。\n"
    "信息使用规则：\n"
    "1. 景点列表里的 ticket（门票）、open（开放时间）、address（地址）可以直接引用。\n"
    "2. 用户问的东西列表里没有时（比如某家火锅店、某条小吃街），"
    "**不要说\"没有资料\"、\"未收录\"、\"抱歉查不到\"这类话**。"
    "改用同城或邻近的景点作为参照，给出方向性建议，"
    "例如\"云南大学那一带的小吃街应该有，逛完顺路找一家\"。"
    "语气要自然，像在给建议而不是在报数据。\n"
    "3. 不要编造具体店名、电话、精确价格或门牌号；"
    "需要精确信息时，提醒用户用地图或点评类应用确认。\n"
    "4. 用户闲聊或开玩笑时，轻松接住，不要硬推景点。"
)


def _read_env_file() -> dict[str, str]:
    """读取 instance/agent.env（KEY=VALUE 格式），文件不存在时返回空字典。"""

    values: dict[str, str] = {}
    try:
        text = ENV_FILE.read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def settings() -> dict[str, str]:
    """环境变量优先，其次读本地配置文件。"""

    file_values = _read_env_file()
    return {
        "api_key": os.getenv("ARK_API_KEY") or file_values.get("ARK_API_KEY", ""),
        "model": os.getenv("ARK_MODEL") or file_values.get("ARK_MODEL", ""),
        "base_url": (
            os.getenv("ARK_BASE_URL")
            or file_values.get("ARK_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/"),
    }


def is_configured() -> bool:
    config = settings()
    return bool(config["api_key"] and config["model"])


def _post_json(url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def ask_model(
    messages: list[dict[str, str]],
    json_mode: bool = False,
    temperature: float = 0.6,
) -> str | None:
    """调用模型返回文本；任何异常都返回 None，由调用方降级。"""

    config = settings()
    if not config["api_key"] or not config["model"]:
        return None

    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        data = _post_json(config["base_url"] + "/chat/completions", payload, config["api_key"])
        return data["choices"][0]["message"]["content"]
    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        OSError,
    ):
        return None


def pick_candidates(
    rows: list[dict[str, Any]],
    message: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """从全部景点中挑出与提问相关的记录。

    命中规则：景点名出现在问题里，或问题里提到了该景点所在城市。
    命中的排在前面，其余按原顺序补齐，保证上下文里既有相关内容也有备选。
    """

    text = message or ""

    def score(row: dict[str, Any]) -> int:
        name = row.get("name") or ""
        if name and name in text:
            return 3
        # 允许"故宫"命中"故宫博物院"这类简称
        for size in (4, 3, 2):
            if len(name) >= size and name[:size] in text:
                return 2
        city = (row.get("city") or "").rstrip("市")
        if city and city in text:
            return 1
        return 0

    ranked = sorted(rows, key=score, reverse=True)
    return ranked[:limit]


def _format_price(cents: Any) -> str:
    """把「分」转换成展示用价格。"""

    if not isinstance(cents, int) or isinstance(cents, bool):
        return "未知"
    if cents == 0:
        return "免费"
    return "¥" + str(cents // 100)


def _attraction_catalogue(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "attraction_id": item["id"],
            "name": item["name"],
            "city": item["city"],
            "ticket": _format_price(item.get("ticket_price_cents")),
            "open": item.get("opening_hours") or "未知",
            "address": item.get("address") or "未知",
            "description": (item.get("description") or "")[:80],
        }
        for item in candidates
    ]


def _clean_days(raw_days: Any, allowed: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """校验模型输出：只保留真实存在的景点，结构不合法直接丢弃。"""

    days: list[dict[str, Any]] = []
    if not isinstance(raw_days, list):
        return days
    for index, raw_day in enumerate(raw_days[:MAX_DAYS], start=1):
        if not isinstance(raw_day, dict):
            continue
        raw_items = raw_day.get("items")
        if not isinstance(raw_items, list):
            continue
        items: list[dict[str, Any]] = []
        seen: set[int] = set()
        for raw_item in raw_items[:3]:
            if not isinstance(raw_item, dict):
                continue
            attraction_id = raw_item.get("attraction_id")
            if not isinstance(attraction_id, int) or isinstance(attraction_id, bool):
                continue
            if attraction_id not in allowed or attraction_id in seen:
                continue
            seen.add(attraction_id)
            attraction = allowed[attraction_id]
            note = raw_item.get("note")
            items.append(
                {
                    "attraction_id": attraction_id,
                    "name": attraction["name"],
                    "city": attraction["city"],
                    "note": note if isinstance(note, str) else "",
                }
            )
        if items:
            days.append({"day": index, "items": items})
    return days


def build_rule_plan(candidates: list[dict[str, Any]], days: int) -> dict[str, Any]:
    """无模型时的规则版行程：按城市分组依次分配。"""

    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        buckets.setdefault(item["city"] or "未分类", []).append(item)

    ordered: list[dict[str, Any]] = []
    for city in sorted(buckets, key=lambda name: len(buckets[name]), reverse=True):
        ordered.extend(buckets[city])

    planned: list[dict[str, Any]] = []
    cursor = 0
    for day in range(1, days + 1):
        items = []
        for item in ordered[cursor:cursor + 2]:
            items.append(
                {
                    "attraction_id": item["id"],
                    "name": item["name"],
                    "city": item["city"],
                    "note": "",
                }
            )
        cursor += 2
        if not items:
            break
        planned.append({"day": day, "items": items})

    cities = [city for city, rows in buckets.items() if rows]
    label = cities[0] if len(cities) == 1 else "精选"
    return {
        "title": label + " " + str(len(planned)) + " 日游",
        "summary": (
            "当前未配置模型密钥，已按城市分组生成规则版草案；"
            "配置 ARK_API_KEY 与 ARK_MODEL 后可获得更贴合需求的行程。"
        ),
        "days": planned,
    }


def plan_itinerary(
    message: str,
    candidates: list[dict[str, Any]],
    days: int,
) -> tuple[dict[str, Any], str]:
    """生成行程，返回 (计划, 来源)，来源为 model 或 rule。"""

    allowed = {item["id"]: item for item in candidates}
    catalogue = _attraction_catalogue(candidates)
    content = ask_model(
        [
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "用户需求：" + message + "\n计划天数：" + str(days)
                    + "\n\n可用景点列表（JSON）：\n"
                    + json.dumps(catalogue, ensure_ascii=False)
                ),
            },
        ],
        json_mode=True,
    )

    if content:
        try:
            raw = json.loads(content)
        except ValueError:
            raw = None
        if isinstance(raw, dict):
            cleaned = _clean_days(raw.get("days"), allowed)
            if cleaned:
                title = raw.get("title")
                summary = raw.get("summary")
                return (
                    {
                        "title": title if isinstance(title, str) and title.strip() else "AI 推荐行程",
                        "summary": summary if isinstance(summary, str) else "",
                        "days": cleaned,
                    },
                    "model",
                )

    return build_rule_plan(candidates, days), "rule"


def to_itinerary_payload(plan: dict[str, Any], start_date: str | None) -> dict[str, Any]:
    """转换成 POST /api/itineraries 可直接使用的结构。"""

    attractions: list[dict[str, Any]] = []
    order = 0
    for day in plan.get("days", []):
        for item in day.get("items", []):
            order += 1
            attractions.append(
                {
                    "attraction_id": item["attraction_id"],
                    "sort_order": order,
                    "notes": item.get("note") or None,
                }
            )

    end_date = None
    if start_date:
        try:
            begin = date.fromisoformat(start_date)
        except ValueError:
            start_date = None
        else:
            end_date = (
                begin + timedelta(days=max(len(plan.get("days", [])), 1) - 1)
            ).isoformat()

    return {
        "title": plan.get("title") or "AI 推荐行程",
        "start_date": start_date,
        "end_date": end_date,
        "notes": plan.get("summary") or None,
        "attractions": attractions,
    }


COPY_SYSTEM_PROMPT = (
    "你是小红书上的旅行博主，写文案幽默、接地气、有点夸张但不假。"
    "要求：第一人称；150-250 字；分成 3-5 个小段，每段开头放一个 emoji；"
    "多用短句和口语；不要写具体价格、店名和地址；"
    "结尾给 3-5 个话题标签，以 # 开头。"
    "只输出文案正文，不要任何解释或标题。"
)


def _plan_outline(plan: dict[str, Any], city: str | None) -> str:
    lines = []
    if city:
        lines.append("目的地：" + city)
    lines.append("行程标题：" + str(plan.get("title") or ""))
    for day in plan.get("days", [])[:7]:
        names = [str(item.get("name")) for item in day.get("items", [])[:5]]
        lines.append("第 " + str(day.get("day")) + " 天：" + "、".join(names))
    return "\n".join(lines)


def build_copywrite_fallback(plan: dict[str, Any], city: str | None) -> str:
    """模型不可用时的模板文案。"""

    title = str(plan.get("title") or "这趟行程")
    days = plan.get("days", []) or []
    chunks = ["🎒 " + title + "，安排上了！"]
    emojis = ["🌿", "🍜", "📸", "🌇", "🚶"]
    for index, day in enumerate(days[:5]):
        names = "、".join(str(item.get("name")) for item in day.get("items", [])[:3])
        if names:
            chunks.append(emojis[index % len(emojis)] + " Day" + str(day.get("day")) + "：" + names)
    chunks.append("💡 主打一个随机应变，走累了就找家小店坐坐，别把行程排太满。")
    tag_city = (city or "").rstrip("市")
    tags = ["#旅行", "#行程分享", "#citywalk"]
    if tag_city:
        tags.insert(0, "#" + tag_city)
    chunks.append(" ".join(tags[:5]))
    return "\n\n".join(chunks)


def write_caption(plan: dict[str, Any], city: str | None) -> tuple[str, str]:
    """生成分享文案，返回 (文案, 来源)。"""

    outline = _plan_outline(plan, city)
    content = ask_model(
        [
            {"role": "system", "content": COPY_SYSTEM_PROMPT},
            {"role": "user", "content": "根据这份行程写一条分享文案：\n" + outline},
        ],
        temperature=0.9,
    )
    if content and content.strip():
        return content.strip(), "model"
    return build_copywrite_fallback(plan, city), "rule"


def chat_reply(
    message: str,
    history: list[dict[str, str]],
    candidates: list[dict[str, Any]],
) -> tuple[str, str]:
    """返回 (回复内容, 来源)。来源为 model 或 rule。"""

    catalogue = _attraction_catalogue(candidates[:MAX_CANDIDATES])
    context = (
        "以下是 TravelMate 景点库中的可用景点（JSON）：\n"
        + json.dumps(catalogue, ensure_ascii=False)
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {"role": "system", "content": context},
    ]
    for item in history[-MAX_HISTORY_ITEMS:]:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content[:MAX_MESSAGE_LENGTH]})
    messages.append({"role": "user", "content": message})

    reply = ask_model(messages, temperature=0.7)
    if reply and reply.strip():
        return reply.strip(), "model"

    if candidates:
        names = "、".join(item["name"] for item in candidates[:5])
        fallback = (
            "AI 助手暂时不可用。你可以先浏览这些景点：" + names
            + "。配置 ARK_API_KEY 与 ARK_MODEL 后即可获得智能问答。"
        )
    else:
        fallback = "AI 助手暂时不可用。景点库还没有数据，请先导入景点。"
    return fallback, "rule"

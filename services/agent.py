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
    "你是 TravelMate 的旅行助手，语气友好、回答简短实用（不超过 120 字）。"
    "只能依据下面提供的景点信息回答；信息里没有的内容要明确说\"暂时没有这项资料\"，"
    "不要编造门票、开放时间或地址。"
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


def _attraction_catalogue(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "attraction_id": item["id"],
            "name": item["name"],
            "city": item["city"],
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

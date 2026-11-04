"""为内置核心城市景点从 Wikimedia Commons 获取真实图片直链。

脚本不抓取搜索结果 HTML，也不需要 API Key。只有 Wikimedia API 返回的、
扩展名为 jpg/jpeg/png 且响应类型为图片的原图 URL 才会写入数据库。
网络失败或找不到合适图片时使用项目本地占位图。
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any

import requests

from app import create_app
from database.connection import db_transaction


TARGET_CITIES = (
    "三亚市",
    "上海市",
    "北京市",
    "南京市",
    "厦门市",
    "哈尔滨市",
    "大连市",
    "天津市",
    "广州市",
    "成都市",
    "昆明市",
    "杭州市",
    "武汉市",
    "济南市",
    "深圳市",
    "苏州市",
    "西安市",
    "重庆市",
    "长沙市",
    "青岛市",
)
PLACEHOLDER_URL = "/static/images/placeholder-attraction.svg"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
IMAGE_SUFFIX = re.compile(r"\.(?:jpe?g|png)$", re.IGNORECASE)
REQUEST_TIMEOUT = 20
MIN_REQUEST_INTERVAL = 1.0


def _search_image(session: requests.Session, name: str, city: str) -> str | None:
    """查询 Commons，返回第一个经过格式校验的原图直链。"""

    base_params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": 6,
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url|mime",
    }
    for search_text in (f"{name} {city}", name):
        params = {**base_params, "gsrsearch": search_text}
        for attempt in range(3):
            response = session.get(COMMONS_API, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code != 429:
                break
            retry_after = int(response.headers.get("Retry-After", "5"))
            time.sleep(min(max(retry_after, 5), 30) * (attempt + 1))
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        pages = payload.get("query", {}).get("pages", {})
        if not isinstance(pages, dict):
            continue

        for page in pages.values():
            if not isinstance(page, dict):
                continue
            imageinfo = page.get("imageinfo")
            if not isinstance(imageinfo, list) or not imageinfo:
                continue
            info = imageinfo[0]
            if not isinstance(info, dict):
                continue
            url = str(info.get("url", "")).strip().split("?", 1)[0]
            mime = str(info.get("mime", "")).lower()
            if IMAGE_SUFFIX.search(url) and mime in {"image/jpeg", "image/png"}:
                return url
    return None


def fetch_images(database: sqlite3.Connection) -> tuple[int, int]:
    """更新核心城市图片，返回（成功数量，回退数量）。"""

    placeholders = ",".join("?" for _ in TARGET_CITIES)
    rows = database.execute(
        f"SELECT id, name, city FROM attractions "
        f"WHERE source = 'core' AND city IN ({placeholders}) ORDER BY id",
        TARGET_CITIES,
    ).fetchall()
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "TravelMate/1.0 (educational project; "
                "image metadata lookup)"
            )
        }
    )
    success = fallback = 0
    for row in rows:
        current_url = str(
            database.execute(
                "SELECT image_url FROM attractions WHERE id = ?", (row["id"],)
            ).fetchone()["image_url"]
            or ""
        )
        if current_url.startswith("https://") and (
            IMAGE_SUFFIX.search(current_url) or "baidu.com" in current_url
        ):
            success += 1
            continue
        image_url = None
        try:
            image_url = _search_image(session, row["name"], row["city"])
        except (requests.RequestException, ValueError) as error:
            print(f"[网络失败] {row['city']} - {row['name']}: {error}")
        if image_url:
            success += 1
        else:
            image_url = PLACEHOLDER_URL
            fallback += 1
        database.execute(
            "UPDATE attractions SET image_url = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (image_url, row["id"]),
        )
        print(f"[{'成功' if image_url != PLACEHOLDER_URL else '占位'}] {row['city']} - {row['name']}")
        time.sleep(MIN_REQUEST_INTERVAL)
    return success, fallback


def main() -> None:
    app = create_app(init_database=False)
    with app.app_context():
        with db_transaction() as database:
            success, fallback = fetch_images(database)
    print(f"图片更新完成：真实图片 {success} 条，占位图 {fallback} 条")


if __name__ == "__main__":
    main()

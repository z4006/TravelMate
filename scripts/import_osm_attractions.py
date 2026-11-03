"""导入合法获取的 OpenStreetMap/Overpass JSON 景点数据。

本脚本只读取本地 JSON，不自动抓取网络数据。这样可以让使用者先确认
下载范围、来源和许可，再按城市分批导入，避免把大型原始数据提交到仓库。
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from app import create_app
from database.attractions import (
    import_elements as database_import_elements,
    migrate_attractions,
    seed_initial_attractions,
)
from database.connection import db_transaction, utc_now


CATEGORY_BY_TAG = {
    "museum": "historical",
    "gallery": "historical",
    "theme_park": "theme-park",
    "zoo": "theme-park",
    "aquarium": "theme-park",
    "park": "natural",
    "nature_reserve": "natural",
    "viewpoint": "natural",
}


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "attraction"


def _element_coordinates(element: dict[str, Any]) -> tuple[float | None, float | None]:
    if isinstance(element.get("lat"), (int, float)) and isinstance(
        element.get("lon"), (int, float)
    ):
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, dict) and isinstance(
        center.get("lat"), (int, float)
    ) and isinstance(center.get("lon"), (int, float)):
        return float(center["lat"]), float(center["lon"])
    return None, None


def _city(tags: dict[str, Any]) -> str:
    return str(
        tags.get("addr:city")
        or tags.get("addr:district")
        or tags.get("addr:province")
        or "未知城市"
    ).strip()


def _address(tags: dict[str, Any]) -> str | None:
    address = tags.get("addr:full")
    if address:
        return str(address).strip()
    parts = [
        str(tags[key]).strip()
        for key in ("addr:province", "addr:city", "addr:district", "addr:street")
        if tags.get(key)
    ]
    return "".join(parts) or None


def normalize_element(element: dict[str, Any]) -> dict[str, Any] | None:
    """将一个 Overpass element 转换为景点导入记录。"""

    tags = element.get("tags")
    if not isinstance(tags, dict) or not isinstance(tags.get("name"), str):
        return None
    name = tags["name"].strip()
    element_type = element.get("type")
    element_id = element.get("id")
    if not name or element_type not in {"node", "way", "relation"}:
        return None
    source_id = f"{element_type}/{element_id}"
    tourism = str(tags.get("tourism", "")).lower()
    historic = str(tags.get("historic", "")).lower()
    category_slug = CATEGORY_BY_TAG.get(tourism, "historical" if historic else "natural")
    latitude, longitude = _element_coordinates(element)
    description = tags.get("description") or tags.get("wikipedia")
    return {
        "name": name,
        "slug": f"osm-{_slug(source_id)}-{_slug(name)}",
        "category_slug": category_slug,
        "city": _city(tags),
        "address": _address(tags),
        "description": str(description).strip() if description else None,
        "opening_hours": str(tags["opening_hours"]).strip()
        if tags.get("opening_hours")
        else None,
        "source": "openstreetmap",
        "source_id": source_id,
        "source_url": f"https://www.openstreetmap.org/{source_id}",
        "latitude": latitude,
        "longitude": longitude,
    }


def import_elements(database, elements: list[dict[str, Any]]) -> tuple[int, int]:
    """幂等导入元素，返回（新增数，更新数）。"""

    categories = {
        row["slug"]: row["id"]
        for row in database.execute(
            "SELECT id, slug FROM attraction_categories"
        ).fetchall()
    }
    now = utc_now()
    inserted = updated = 0
    for element in elements:
        record = normalize_element(element)
        if record is None:
            continue
        category_id = categories[record["category_slug"]]
        existing = database.execute(
            "SELECT id FROM attractions WHERE source = ? AND source_id = ?",
            (record["source"], record["source_id"]),
        ).fetchone()
        values = (
            record["name"],
            record["slug"],
            category_id,
            record["city"],
            record["address"],
            record["description"],
            record["opening_hours"],
            record["source_url"],
            record["latitude"],
            record["longitude"],
            now,
        )
        if existing:
            database.execute(
                "UPDATE attractions SET name = ?, slug = ?, category_id = ?, "
                "city = ?, address = ?, description = ?, opening_hours = ?, "
                "source_url = ?, latitude = ?, longitude = ?, updated_at = ? "
                "WHERE id = ?",
                (*values, existing["id"]),
            )
            updated += 1
        else:
            database.execute(
                "INSERT INTO attractions "
                "(name, slug, category_id, city, address, description, "
                "opening_hours, source, source_id, source_url, latitude, longitude, "
                "status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'openstreetmap', ?, ?, ?, ?, "
                "'active', ?, ?)",
                (
                    record["name"],
                    record["slug"],
                    category_id,
                    record["city"],
                    record["address"],
                    record["description"],
                    record["opening_hours"],
                    record["source_id"],
                    record["source_url"],
                    record["latitude"],
                    record["longitude"],
                    now,
                    now,
                ),
            )
            inserted += 1
    return inserted, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 OSM/Overpass JSON 景点数据")
    parser.add_argument("input", type=Path, help="本地 Overpass JSON 文件路径")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
    elements = payload.get("elements") if isinstance(payload, dict) else None
    if not isinstance(elements, list):
        raise ValueError("输入必须是包含 elements 数组的 Overpass JSON")

    app = create_app(init_database=False)
    with app.app_context():
        with db_transaction() as database:
            migrate_attractions(database)
            seed_initial_attractions(database)
            records = [
                record
                for element in elements
                if (record := normalize_element(element)) is not None
            ]
            inserted, updated = database_import_elements(database, records)
        total = database.execute("SELECT COUNT(*) FROM attractions").fetchone()[0]
    print(f"新增 {inserted} 条，更新 {updated} 条，当前景点总数：{total}")


if __name__ == "__main__":
    main()

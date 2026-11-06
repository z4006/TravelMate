"""把核心数据集里尚未入库的景点增量插入数据库（只增不改，可重复执行）。

与 rebuild_core_attractions 的区别：
- 不删除任何现有记录，景点 id、坐标、图片、收藏、行程全部保持原样；
- 只插入 (name, city) 在库中不存在的记录，重复执行安全；
- 新记录直接带上城市坐标，并优先使用已存在的本地图片，远程图统一分配风景图。

用法（服务器）：
    TRAVELMATE_DATABASE=/var/lib/travelmate/travelmate.db \
        /opt/travelmate/.venv/bin/python -m scripts.add_missing_attractions --dry-run
    去掉 --dry-run 即真正写入。
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "core_attractions.json"
IMG_DIR = ROOT / "static" / "images" / "attractions"
SCENERY = sorted(p.name for p in IMG_DIR.glob("scenery-*.jpg"))
SCENERY_TOTAL = len(SCENERY) or 1
SPREAD = 0.02


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "attraction"


def _offset(name: str) -> tuple[float, float]:
    digest = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16)
    lat = ((digest % 1000) / 1000 - 0.5) * 2 * SPREAD
    lng = (((digest // 1000) % 1000) / 1000 - 0.5) * 2 * SPREAD
    return lat, lng


def _pick_image(name: str, raw: str) -> str:
    """本地图存在就用，否则给一张风景图。"""

    raw = (raw or "").strip()
    if raw.startswith("/static/"):
        if (ROOT / raw.lstrip("/")).is_file():
            return raw
    if raw.startswith("http") or not raw:
        digest = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16)
        return "/static/images/attractions/" + SCENERY[digest % SCENERY_TOTAL]
    return raw


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    from app import create_app
    from data.city_coords import CITY_COORDS, normalize_city
    from database.connection import db_transaction, get_db

    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    app = create_app(init_database=False)

    with app.app_context():
        database = get_db()
        existing = {
            (row["name"], row["city"])
            for row in database.execute("SELECT name, city FROM attractions")
        }
        categories = {
            row["slug"]: row["id"]
            for row in database.execute("SELECT id, slug FROM attraction_categories")
        }

        pending = [r for r in records if (r["name"], r["city"]) not in existing]
        print(f"数据集 {len(records)} 条，库中已有 {len(existing)} 条，待插入 {len(pending)} 条")

        unknown = sorted({r["category_slug"] for r in pending} - set(categories))
        if unknown:
            raise SystemExit(f"数据库缺少分类: {unknown}")

        if dry_run:
            for record in pending[:10]:
                print("  将插入:", record["city"], record["name"])
            print("  ...")
            return

        inserted = 0
        with db_transaction():
            for index, record in enumerate(pending, start=1):
                city = record.get("city") or ""
                base = CITY_COORDS.get(normalize_city(city))
                latitude = longitude = None
                if base is not None:
                    lat_offset, lng_offset = _offset(record["name"])
                    latitude = round(base[1] + lat_offset, 6)
                    longitude = round(base[0] + lng_offset, 6)

                image_url = _pick_image(record["name"], record.get("image_url"))

                database.execute(
                    """
                    INSERT INTO attractions (
                        name, slug, category_id, city, address, phone, description,
                        ticket_price_cents, opening_hours, image_url, latitude, longitude,
                        source, source_id, source_url, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'core', ?, ?, 'active',
                        datetime('now'), datetime('now'))
                    """,
                    (
                        record["name"],
                        f"core-add-{index:03d}-{_slug(city)}-{_slug(record['name'])}",
                        categories[record["category_slug"]],
                        city,
                        record.get("address"),
                        record.get("phone"),
                        record["description"],
                        record.get("ticket_price_cents"),
                        record.get("opening_hours"),
                        image_url,
                        latitude,
                        longitude,
                        f"core-add/{index}",
                        image_url,
                    ),
                )
                inserted += 1

        total = database.execute("SELECT COUNT(*) FROM attractions").fetchone()[0]
        cities = database.execute(
            "SELECT COUNT(DISTINCT city) FROM attractions"
        ).fetchone()[0]

    print(f"插入完成: {inserted} 条")
    print(f"当前总数: {total} 条，城市 {cities} 个")


if __name__ == "__main__":
    main()

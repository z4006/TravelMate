"""用六城核心景点数据重建本地演示数据库。"""

import re
import sqlite3
import json
from pathlib import Path

from app import create_app
from database.attractions import migrate_attractions, seed_initial_attractions
from database.connection import db_transaction


DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "core_attractions.json"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "attraction"


def rebuild(database: sqlite3.Connection) -> tuple[int, int]:
    """删除六城旧数据并写入精选数据，返回（删除数，新增数）。"""

    deleted = database.execute(
        "DELETE FROM attractions WHERE source = 'core'"
    ).rowcount
    category_ids = {
        row["slug"]: row["id"]
        for row in database.execute(
            "SELECT id, slug FROM attraction_categories"
        ).fetchall()
    }
    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    for index, record in enumerate(records, start=1):
        source_id = f"core/{index}"
        database.execute(
            """
            INSERT INTO attractions (
                name, slug, category_id, city, description, image_url,
                source, source_id, source_url, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'core', ?, ?, 'active', datetime('now'), datetime('now'))
            """,
            (
                record["name"],
                f"core-{index:03d}-{_slug(record['city'])}-{_slug(record['name'])}",
                category_ids[record["category_slug"]],
                record["city"],
                record["description"],
                record["image_url"],
                source_id,
                record["image_url"],
            ),
        )
    return deleted, len(records)


def main() -> None:
    app = create_app(init_database=False)
    with app.app_context():
        with db_transaction() as database:
            migrate_attractions(database)
            seed_initial_attractions(database)
            deleted, inserted = rebuild(database)
        print(f"已删除旧景点 {deleted} 条，写入核心景点 {inserted} 条")


if __name__ == "__main__":
    main()

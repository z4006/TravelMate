"""景点与分类的数据访问、迁移和演示数据初始化。"""

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from database.connection import utc_now


CORE_DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "core_attractions.json"
_CORE_VERSION_KEY = "core_attractions_sha256"
_CORE_CATEGORIES = {
    "historical": ("历史古迹", "historical"),
    "natural": ("自然风光", "natural"),
    "theme-park": ("主题乐园", "theme-park"),
}


def migrate_attractions(database: sqlite3.Connection) -> None:
    """幂等创建景点模块表和索引，不修改或删除已有数据。"""

    database.execute(
        """
        CREATE TABLE IF NOT EXISTS attraction_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE
        )
        """
    )
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS attractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            category_id INTEGER NOT NULL,
            city TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            description TEXT,
            ticket_price_cents INTEGER CHECK (
                ticket_price_cents IS NULL OR ticket_price_cents >= 0
            ),
            opening_hours TEXT,
            image_url TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            source_id TEXT,
            source_url TEXT,
            latitude REAL,
            longitude REAL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'inactive')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (category_id)
                REFERENCES attraction_categories (id) ON DELETE RESTRICT
        )
        """
    )
    columns = {
        row["name"]
        for row in database.execute("PRAGMA table_info(attractions)").fetchall()
    }
    for column, definition in (
        ("source", "TEXT NOT NULL DEFAULT 'manual'"),
        ("source_id", "TEXT"),
        ("source_url", "TEXT"),
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("phone", "TEXT"),
    ):
        if column not in columns:
            database.execute(
                f"ALTER TABLE attractions ADD COLUMN {column} {definition}"
            )
    database.execute(
        "CREATE INDEX IF NOT EXISTS ix_attractions_status_city_category_id "
        "ON attractions (status, city, category_id, id)"
    )
    database.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_attractions_source_id "
        "ON attractions (source, source_id) WHERE source_id IS NOT NULL"
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def import_elements(
    database: sqlite3.Connection, elements: list[dict[str, Any]]
) -> tuple[int, int]:
    """幂等导入外部景点记录，返回（新增数，更新数）。"""

    categories = {
        row["slug"]: row["id"]
        for row in database.execute(
            "SELECT id, slug FROM attraction_categories"
        ).fetchall()
    }
    now = utc_now()
    inserted = updated = 0
    for record in elements:
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
                "source_url = ?, latitude = ?, longitude = ?, image_url = ?, "
                "updated_at = ? "
                "WHERE id = ?",
                (
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
                    record["image_url"],
                    now,
                    existing["id"],
                ),
            )
            updated += 1
        else:
            database.execute(
                "INSERT INTO attractions "
                "(name, slug, category_id, city, address, description, "
                "opening_hours, image_url, source, source_id, source_url, latitude, longitude, "
                "status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'openstreetmap', ?, ?, ?, ?, "
                "'active', ?, ?)",
                (
                    record["name"],
                    record["slug"],
                    category_id,
                    record["city"],
                    record["address"],
                    record["description"],
                    record["opening_hours"],
                    record["image_url"],
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


def list_attractions(
    database: sqlite3.Connection,
    category_slug: str | None,
    city: str | None,
    keyword: str | None,
    limit: int,
    offset: int,
) -> tuple[list[sqlite3.Row], int]:
    """按筛选条件分页查询公开景点。"""

    conditions = ["a.status = 'active'"]
    parameters: list[Any] = []
    if category_slug:
        conditions.append("c.slug = ?")
        parameters.append(category_slug)
    if city:
        conditions.append("a.city LIKE ? ESCAPE '\\'")
        parameters.append(f"%{_escape_like(city)}%")
    if keyword:
        pattern = f"%{_escape_like(keyword)}%"
        conditions.append(
            "(a.name LIKE ? ESCAPE '\\' OR a.description LIKE ? ESCAPE '\\')"
        )
        parameters.extend((pattern, pattern))
    where_clause = " AND ".join(conditions)
    from_clause = (
        "FROM attractions AS a "
        "JOIN attraction_categories AS c ON c.id = a.category_id "
        f"WHERE {where_clause} "
    )
    select_clause = (
        "SELECT a.id, a.name, a.slug, a.city, a.address, a.phone, "
        "a.description, "
        "a.ticket_price_cents, a.opening_hours, a.image_url, "
        "a.source, a.source_id, a.source_url, a.latitude, a.longitude, "
        "a.created_at, a.updated_at, c.id AS category_id, "
        "c.name AS category_name, c.slug AS category_slug "
    )
    rows = database.execute(
        select_clause
        + from_clause
        + "ORDER BY a.name COLLATE NOCASE ASC, a.id ASC LIMIT ? OFFSET ?",
        (*parameters, limit, offset),
    ).fetchall()
    total = database.execute(
        "SELECT COUNT(*) " + from_clause,
        parameters,
    ).fetchone()[0]
    return rows, int(total)


def list_categories(database: sqlite3.Connection) -> list[sqlite3.Row]:
    """按名称稳定排序查询分类。"""

    return database.execute(
        "SELECT id, name, slug FROM attraction_categories "
        "ORDER BY name COLLATE NOCASE ASC, id ASC"
    ).fetchall()


def get_attraction_by_id(
    database: sqlite3.Connection,
    attraction_id: int,
) -> sqlite3.Row | None:
    """查询单个公开景点。"""

    return database.execute(
        "SELECT a.id, a.name, a.slug, a.city, a.address, a.phone, "
        "a.description, "
        "a.ticket_price_cents, a.opening_hours, a.image_url, "
        "a.source, a.source_id, a.source_url, a.latitude, a.longitude, "
        "a.created_at, a.updated_at, c.id AS category_id, "
        "c.name AS category_name, c.slug AS category_slug "
        "FROM attractions AS a "
        "JOIN attraction_categories AS c ON c.id = a.category_id "
        "WHERE a.id = ? AND a.status = 'active'",
        (attraction_id,),
    ).fetchone()


_INITIAL_CATEGORIES = (
    ("历史古迹", "historical"),
    ("自然风光", "natural"),
    ("主题乐园", "theme-park"),
)

_INITIAL_ATTRACTIONS = (
    (
        "西湖",
        "west-lake",
        "natural",
        "杭州市",
        "杭州市西湖风景名胜区",
        "杭州代表性的湖泊与风景名胜区。",
    ),
    (
        "故宫博物院",
        "palace-museum",
        "historical",
        "北京市",
        "北京市东城区景山前街 4 号",
        "位于北京中轴线中心区域的综合性博物馆。",
    ),
    (
        "八达岭长城",
        "badaling-great-wall",
        "historical",
        "北京市",
        "北京市延庆区八达岭镇",
        "明长城的重要组成部分和代表性段落。",
    ),
    (
        "张家界国家森林公园",
        "zhangjiajie-national-forest-park",
        "natural",
        "张家界市",
        "湖南省张家界市武陵源区",
        "以峰林地貌和自然景观著称的国家森林公园。",
    ),
    (
        "上海迪士尼乐园",
        "shanghai-disneyland",
        "theme-park",
        "上海市",
        "上海市浦东新区川沙新镇",
        "位于上海国际旅游度假区的主题乐园。",
    ),
)


def seed_initial_attractions(database: sqlite3.Connection) -> None:
    """幂等写入演示分类和景点；不会覆盖已有同 slug 记录。"""

    for name, slug in _INITIAL_CATEGORIES:
        database.execute(
            "INSERT INTO attraction_categories (name, slug) VALUES (?, ?) "
            "ON CONFLICT(slug) DO NOTHING",
            (name, slug),
        )

    category_ids = {
        row["slug"]: row["id"]
        for row in database.execute(
            "SELECT id, slug FROM attraction_categories"
        ).fetchall()
    }
    now = utc_now()
    for name, slug, category_slug, city, address, description in (
        _INITIAL_ATTRACTIONS
    ):
        database.execute(
            "INSERT INTO attractions "
            "(name, slug, category_id, city, address, description, "
            "ticket_price_cents, opening_hours, image_url, status, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 'active', ?, ?) "
            "ON CONFLICT(slug) DO NOTHING",
            (
                name,
                slug,
                category_ids[category_slug],
                city,
                address,
                description,
                now,
                now,
            ),
        )


def _core_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-") or "attraction"


def _core_records() -> list[dict[str, Any]]:
    """读取仓库内核心城市景点数据，文件缺失或损坏时返回空列表。"""

    try:
        raw = CORE_DATA_FILE.read_bytes()
    except OSError:
        return []
    try:
        records = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    return records if isinstance(records, list) else []


def _core_digest(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_state_table(database: sqlite3.Connection) -> None:
    database.execute(
        "CREATE TABLE IF NOT EXISTS app_state ("
        "key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )


def core_sync_state(database: sqlite3.Connection) -> str | None:
    """读取已写入的核心景点数据版本指纹。"""

    _ensure_state_table(database)
    row = database.execute(
        "SELECT value FROM app_state WHERE key = ?", (_CORE_VERSION_KEY,)
    ).fetchone()
    return row["value"] if row else None


def rebuild_core_attractions(database: sqlite3.Connection) -> tuple[int, int]:
    """用仓库 JSON 重建核心城市景点，返回（删除数，写入数）。"""

    records = _core_records()
    if not records:
        return 0, 0
    for slug, (name, _slug) in _CORE_CATEGORIES.items():
        database.execute(
            "INSERT INTO attraction_categories (name, slug) VALUES (?, ?) "
            "ON CONFLICT(slug) DO NOTHING",
            (name, _slug),
        )
    category_ids = {
        row["slug"]: row["id"]
        for row in database.execute(
            "SELECT id, slug FROM attraction_categories"
        ).fetchall()
    }
    deleted = database.execute(
        "DELETE FROM attractions WHERE source = 'core'"
    ).rowcount
    now = utc_now()
    for index, record in enumerate(records, start=1):
        category_id = category_ids.get(record.get("category_slug") or "")
        if category_id is None:
            category_id = next(iter(category_ids.values()))
        database.execute(
            "INSERT INTO attractions ("
            "name, slug, category_id, city, address, phone, description, "
            "ticket_price_cents, opening_hours, image_url, source, source_id, "
            "source_url, status, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'core', ?, ?, 'active', ?, ?)",
            (
                record.get("name") or "未命名景点",
                f"core-{index:03d}-{_core_slug(record.get('city'))}-"
                f"{_core_slug(record.get('name'))}",
                category_id,
                record.get("city") or "",
                record.get("address"),
                record.get("phone"),
                record.get("description") or "",
                record.get("ticket_price_cents"),
                record.get("opening_hours"),
                record.get("image_url"),
                f"core/{index}",
                record.get("image_url"),
                now,
                now,
            ),
        )
    # 清掉与核心数据同名同城的演示景点，避免列表出现重复卡片
    database.execute(
        "DELETE FROM attractions WHERE source <> 'core' AND EXISTS ("
        "SELECT 1 FROM attractions AS core WHERE core.source = 'core' "
        "AND core.city = attractions.city AND core.name = attractions.name)"
    )
    _ensure_state_table(database)
    database.execute(
        "INSERT INTO app_state (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
        "updated_at = excluded.updated_at",
        (_CORE_VERSION_KEY, _core_digest(records), now),
    )
    return deleted, len(records)


def sync_core_attractions(database: sqlite3.Connection) -> int:
    """数据版本与仓库 JSON 不一致时自动重建，返回写入条数（无需重建为 0）。"""

    records = _core_records()
    if not records:
        return 0
    expected = _core_digest(records)
    current = core_sync_state(database)
    count = database.execute(
        "SELECT COUNT(*) FROM attractions WHERE source = 'core'"
    ).fetchone()[0]
    if current == expected and int(count) == len(records):
        return 0
    _, inserted = rebuild_core_attractions(database)
    return inserted

"""景点与分类的数据访问、迁移和演示数据初始化。"""

import sqlite3
from typing import Any

from database.connection import utc_now


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

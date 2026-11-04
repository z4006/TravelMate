"""为演示数据补充门票与开放时间（幂等）。

说明：
- 只处理字段为空（NULL）的记录，不覆盖已有真实数据；
- 价格与时间按景点类型 + 名称关键词估算，结果稳定（同一条记录每次一致）；
- 生成的是**演示数据**，不代表真实票价，页面应注明仅供参考。

用法：
    .venv/bin/python -m scripts.fill_demo_fields
"""

import hashlib
import sqlite3

from app import create_app
from database.connection import db_transaction, get_db

FREE_KEYWORDS = (
    "博物馆", "纪念馆", "陈列馆", "美术馆", "展览馆", "科技馆",
    "公园", "湿地", "广场", "步行街", "老街", "街区", "巷",
    "湖", "海滨", "沙滩", "海滩", "古镇", "古城", "村",
)
THEME_KEYWORDS = ("乐园", "迪士尼", "环球", "欢乐谷", "海洋世界", "水族馆", "动物园")
MOUNTAIN_KEYWORDS = ("山", "峰", "峡谷", "溶洞", "森林", "瀑布", "岛", "草原", "沙漠")
HERITAGE_KEYWORDS = ("寺", "庙", "塔", "阁", "宫", "陵", "祠", "园", "楼", "关", "长城", "遗址")

SIGHT_HOURS = ("08:00-17:00", "08:30-17:30", "09:00-17:00", "08:00-18:00", "09:00-18:00")
ALL_DAY_WORDS = ("公园", "湖", "街", "广场", "古城", "古镇", "村", "湿地", "海滨", "沙滩")


def _stable_int(value: str) -> int:
    return int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16)


def estimate_price(name: str, slug: str, category_slug: str) -> int:
    seed = _stable_int(slug or name)

    if category_slug == "theme-park" or any(word in name for word in THEME_KEYWORDS):
        return (200 + seed % 220) * 100

    if any(word in name for word in FREE_KEYWORDS):
        if seed % 10 < 7:
            return 0
        return (30 + seed % 31) * 100

    if any(word in name for word in MOUNTAIN_KEYWORDS):
        return (60 + seed % 91) * 100

    if any(word in name for word in HERITAGE_KEYWORDS):
        return (30 + seed % 91) * 100

    return (40 + seed % 61) * 100


def estimate_hours(name: str, slug: str) -> str:
    if any(word in name for word in ALL_DAY_WORDS):
        return "全天开放"
    seed = _stable_int(slug or name)
    return SIGHT_HOURS[seed % len(SIGHT_HOURS)]


def fill(database: sqlite3.Connection) -> tuple[int, int]:
    rows = database.execute(
        "SELECT a.id, a.name, a.slug, a.ticket_price_cents, a.opening_hours, "
        "c.slug AS category_slug "
        "FROM attractions a JOIN attraction_categories c ON c.id = a.category_id "
        "WHERE a.ticket_price_cents IS NULL "
        "   OR a.opening_hours IS NULL OR a.opening_hours = ''"
    ).fetchall()

    price_filled = hours_filled = 0
    for row in rows:
        if row["ticket_price_cents"] is None:
            database.execute(
                "UPDATE attractions SET ticket_price_cents = ? WHERE id = ?",
                (estimate_price(row["name"], row["slug"], row["category_slug"]), row["id"]),
            )
            price_filled += 1
        if not row["opening_hours"]:
            database.execute(
                "UPDATE attractions SET opening_hours = ? WHERE id = ?",
                (estimate_hours(row["name"], row["slug"]), row["id"]),
            )
            hours_filled += 1
    return price_filled, hours_filled


def dedupe(database: sqlite3.Connection) -> int:
    """删除与 core 数据同名同城的 manual 重复记录。"""

    cursor = database.execute(
        "DELETE FROM attractions WHERE source = 'manual' AND EXISTS ("
        "  SELECT 1 FROM attractions core "
        "  WHERE core.source = 'core' AND core.name = attractions.name "
        "    AND core.city = attractions.city)"
    )
    return cursor.rowcount


def main() -> None:
    app = create_app(init_database=False)
    with app.app_context():
        with db_transaction():
            removed = dedupe(get_db())
            price_filled, hours_filled = fill(get_db())
        total = get_db().execute("SELECT COUNT(*) FROM attractions").fetchone()[0]
        no_price = get_db().execute(
            "SELECT COUNT(*) FROM attractions WHERE ticket_price_cents IS NULL"
        ).fetchone()[0]
        no_hours = get_db().execute(
            "SELECT COUNT(*) FROM attractions WHERE opening_hours IS NULL OR opening_hours = ''"
        ).fetchone()[0]
    print(f"清理重复景点 {removed} 条")
    print(f"补充票价 {price_filled} 条，补充开放时间 {hours_filled} 条")
    print(f"当前景点 {total} 条，缺票价 {no_price} 条，缺开放时间 {no_hours} 条")


if __name__ == "__main__":
    main()

"""为景点补充演示用经纬度（城市中心 + 微小偏移）。

说明：
- 坐标来自 data/city_coords.py 的城市中心（WGS84），仅用于示意定位，不用于导航；
- 同一城市内的景点按名称哈希做 ±0.02° 的偏移，避免所有点重合；
- 只处理 latitude / longitude 为空的记录，不覆盖真实数据。

用法（服务器，root）：
    TRAVELMATE_DATABASE=/var/lib/travelmate/travelmate.db \
        /opt/travelmate/.venv/bin/python -m scripts.fill_demo_coords
"""

import hashlib
import sqlite3

from app import create_app
from data.city_coords import CITY_COORDS, normalize_city
from database.connection import db_transaction, get_db

SPREAD = 0.02  # 约 2 公里


def _offset(name: str) -> tuple[float, float]:
    digest = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16)
    lat = ((digest % 1000) / 1000 - 0.5) * 2 * SPREAD
    lng = (((digest // 1000) % 1000) / 1000 - 0.5) * 2 * SPREAD
    return lat, lng


def fill(database: sqlite3.Connection) -> tuple[int, int]:
    rows = database.execute(
        "SELECT id, name, city FROM attractions "
        "WHERE latitude IS NULL OR longitude IS NULL"
    ).fetchall()

    filled = skipped = 0
    for row in rows:
        city = normalize_city(row["city"] or "")
        base = CITY_COORDS.get(city)
        if base is None:
            skipped += 1
            continue
        lat_offset, lng_offset = _offset(row["name"])
        lat = round(base[1] + lat_offset, 6)
        lng = round(base[0] + lng_offset, 6)
        database.execute(
            "UPDATE attractions SET latitude = ?, longitude = ? WHERE id = ?",
            (lat, lng, row["id"]),
        )
        filled += 1
    return filled, skipped


def main() -> None:
    app = create_app(init_database=False)
    with app.app_context():
        with db_transaction():
            filled, skipped = fill(get_db())
        total = get_db().execute(
            "SELECT COUNT(*) FROM attractions WHERE latitude IS NOT NULL"
        ).fetchone()[0]
    print(f"补充坐标 {filled} 条，跳过 {skipped} 条（城市无坐标表）")
    print(f"当前有坐标的景点：{total}")


if __name__ == "__main__":
    main()

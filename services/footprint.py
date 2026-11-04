"""旅行足迹聚合服务（任务 C）。

数据来源全部是已有业务表，不新增数据库表：
1. favorites —— 用户收藏的景点，视为「已打卡 / 已收藏」的城市；
2. itineraries + itinerary_attractions —— 用户规划过的行程里的景点；
3. attractions —— 全量景点，用于给地图提供「全部可点亮城市」底色。

对外输出统一结构，前端只负责画图和合成海报，不再做任何聚合计算。
"""

from __future__ import annotations

import sqlite3
from typing import Any

from data.city_coords import city_coords, normalize_city

# 旅行等级阈值：(城市数, 称号)
LEVELS = (
    (1, "初出茅庐"),
    (3, "周末旅人"),
    (5, "城市猎人"),
    (8, "资深驴友"),
    (12, "环游达人"),
    (20, "旅行家"),
    (30, "环球旅神"),
)


def _level_for(city_count: int) -> dict[str, Any]:
    title = "宅家观望"
    current = 0
    for threshold, name in LEVELS:
        if city_count >= threshold:
            current = threshold
            title = name
    next_threshold = None
    for threshold, _name in LEVELS:
        if threshold > city_count:
            next_threshold = threshold
            break
    return {
        "title": title,
        "cities": city_count,
        "next_threshold": next_threshold,
        "progress": 0.0 if not next_threshold else round(
            (city_count - current) / float(next_threshold - current), 3
        ),
    }


def _rows(database: sqlite3.Connection, sql: str, params: tuple) -> list[sqlite3.Row]:
    """表不存在时返回空列表，保证足迹页在空库下也能渲染。"""

    try:
        return database.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []


def _attraction_columns(database: sqlite3.Connection) -> set[str]:
    try:
        return {
            row["name"]
            for row in database.execute("PRAGMA table_info(attractions)").fetchall()
        }
    except sqlite3.OperationalError:
        return set()


def build_footprint(database: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """汇总某位用户的旅行足迹。"""

    columns = _attraction_columns(database)
    has_city = "city" in columns

    favorite_rows = _rows(
        database,
        "SELECT a.city AS city, COUNT(*) AS total FROM favorites f "
        "JOIN attractions a ON a.id = f.attraction_id "
        "WHERE f.user_id = ? GROUP BY a.city",
        (user_id,),
    ) if has_city else []
    favorite_cities: dict[str, int] = {}
    for row in favorite_rows:
        key = normalize_city(row["city"])
        if key:
            favorite_cities[key] = favorite_cities.get(key, 0) + int(row["total"] or 0)

    itinerary_rows = _rows(
        database,
        "SELECT a.city AS city, COUNT(*) AS total FROM itinerary_attractions ia "
        "JOIN itineraries i ON i.id = ia.itinerary_id "
        "JOIN attractions a ON a.id = ia.attraction_id "
        "WHERE i.user_id = ? GROUP BY a.city",
        (user_id,),
    ) if has_city else []
    itinerary_cities: dict[str, int] = {}
    for row in itinerary_rows:
        key = normalize_city(row["city"])
        if key:
            itinerary_cities[key] = itinerary_cities.get(key, 0) + int(row["total"] or 0)

    universe_rows = _rows(
        database,
        "SELECT a.city AS city, COUNT(*) AS total FROM attractions a "
        "WHERE a.city IS NOT NULL AND TRIM(a.city) <> '' GROUP BY a.city",
        (),
    ) if has_city else []
    universe: dict[str, dict[str, Any]] = {}
    for row in universe_rows:
        raw = row["city"]
        key = normalize_city(raw)
        if not key:
            continue
        item = universe.setdefault(key, {"raw": raw, "attractions": 0})
        item["attractions"] += int(row["total"] or 0)

    itinerary_total = _rows(
        database,
        "SELECT COUNT(*) AS total FROM itineraries WHERE user_id = ?",
        (user_id,),
    )
    itinerary_count = int(itinerary_total[0]["total"] or 0) if itinerary_total else 0

    visited_names = set(favorite_cities) | set(itinerary_cities)
    cities: list[dict[str, Any]] = []
    for name in sorted(visited_names):
        base = universe.get(name, {"raw": name, "attractions": 0})
        coords = city_coords(name)
        cities.append(
            {
                "name": name,
                "raw": base.get("raw") or name,
                "lon": coords[0] if coords else None,
                "lat": coords[1] if coords else None,
                "favorite_count": favorite_cities.get(name, 0),
                "itinerary_count": itinerary_cities.get(name, 0),
                "attraction_count": base.get("attractions", 0),
                "source": "favorite" if name in favorite_cities else "itinerary",
            }
        )
    cities.sort(
        key=lambda item: item["favorite_count"] + item["itinerary_count"],
        reverse=True,
    )

    background: list[dict[str, Any]] = []
    for name, base in universe.items():
        coords = city_coords(name)
        background.append(
            {
                "name": name,
                "raw": base.get("raw") or name,
                "lon": coords[0] if coords else None,
                "lat": coords[1] if coords else None,
                "attractions": base.get("attractions", 0),
                "visited": name in visited_names,
            }
        )
    background.sort(key=lambda item: item["attractions"], reverse=True)

    city_count = len(cities)
    total_cities = len(universe)

    return {
        "cities": cities,
        "background": background,
        "stats": {
            "city_count": city_count,
            "favorite_count": sum(favorite_cities.values()),
            "itinerary_count": itinerary_count,
            "itinerary_attraction_count": sum(itinerary_cities.values()),
            "total_cities": total_cities,
            "coverage": round(city_count / float(total_cities) * 100, 1)
            if total_cities
            else 0.0,
        },
        "level": _level_for(city_count),
    }

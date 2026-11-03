"""从合法获取的 OpenStreetMap PBF 文件导入旅游和历史景点。"""

import argparse
from pathlib import Path
from typing import Any

import osmium

from app import create_app
from database.attractions import (
    import_elements,
    migrate_attractions,
    seed_initial_attractions,
)
from database.connection import db_transaction
from scripts.import_osm_attractions import normalize_element


class AttractionHandler(osmium.SimpleHandler):
    """提取带名称的旅游或历史对象，并转换为导入器记录。"""

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict[str, Any]] = []

    @staticmethod
    def _tags(tags: Any) -> dict[str, str]:
        return {str(key): str(value) for key, value in tags}

    @staticmethod
    def _coordinates(nodes: Any) -> tuple[float | None, float | None]:
        coordinates = [
            (float(node.lat), float(node.lon))
            for node in nodes
            if node.location.valid()
        ]
        if not coordinates:
            return None, None
        latitude = sum(item[0] for item in coordinates) / len(coordinates)
        longitude = sum(item[1] for item in coordinates) / len(coordinates)
        return latitude, longitude

    def _append(
        self,
        element_type: str,
        element_id: int,
        tags: Any,
        latitude: float | None,
        longitude: float | None,
    ) -> None:
        tag_map = self._tags(tags)
        if not tag_map.get("name"):
            return
        if not tag_map.get("tourism") and not tag_map.get("historic"):
            return
        self.elements.append(
            {
                "type": element_type,
                "id": element_id,
                "lat": latitude,
                "lon": longitude,
                "tags": tag_map,
            }
        )

    def node(self, node: Any) -> None:
        latitude = float(node.location.lat) if node.location.valid() else None
        longitude = float(node.location.lon) if node.location.valid() else None
        self._append("node", node.id, node.tags, latitude, longitude)

    def way(self, way: Any) -> None:
        latitude, longitude = self._coordinates(way.nodes)
        self._append("way", way.id, way.tags, latitude, longitude)

    def relation(self, relation: Any) -> None:
        self._append("relation", relation.id, relation.tags, None, None)


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 OSM PBF 景点数据")
    parser.add_argument("input", type=Path, help="本地 OSM PBF 文件路径")
    parser.add_argument(
        "--city",
        default=None,
        help="区域文件的城市回退值，例如：北京市",
    )
    parser.add_argument(
        "--city-bbox",
        nargs=4,
        type=float,
        metavar=("MIN_LAT", "MIN_LON", "MAX_LAT", "MAX_LON"),
        help="只导入指定城市边界内的景点",
    )
    args = parser.parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(f"找不到 OSM PBF 文件：{args.input}")

    handler = AttractionHandler()
    handler.apply_file(str(args.input), locations=True)
    records = [
        record
        for element in handler.elements
        if (record := normalize_element(element)) is not None
    ]
    fallback_city = args.city
    if fallback_city is None and "beijing" in args.input.stem.lower():
        fallback_city = "北京市"
    if fallback_city:
        for record in records:
            record["city"] = fallback_city
    if args.city_bbox:
        min_lat, min_lon, max_lat, max_lon = args.city_bbox
        records = [
            record
            for record in records
            if record["latitude"] is not None
            and record["longitude"] is not None
            and min_lat <= record["latitude"] <= max_lat
            and min_lon <= record["longitude"] <= max_lon
        ]

    app = create_app(init_database=False)
    with app.app_context():
        with db_transaction() as database:
            migrate_attractions(database)
            seed_initial_attractions(database)
            inserted, updated = import_elements(database, records)
        total = database.execute("SELECT COUNT(*) FROM attractions").fetchone()[0]
    print(
        f"读取 {len(records)} 条，新增 {inserted} 条，"
        f"更新 {updated} 条，当前景点总数：{total}"
    )


if __name__ == "__main__":
    main()

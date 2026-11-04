import json
from collections import Counter
from pathlib import Path


def test_core_dataset_has_complete_records_for_core_cities():
    data_file = Path(__file__).parents[1] / "data" / "core_attractions.json"
    records = json.loads(data_file.read_text(encoding="utf-8"))
    counts = Counter(record["city"] for record in records)

    expected_cities = {
        "北京市",
        "上海市",
        "广州市",
        "深圳市",
        "成都市",
        "西安市",
    }
    assert expected_cities <= counts.keys()
    assert all(counts[city] == 20 for city in expected_cities)
    assert all(count > 0 for count in counts.values())
    assert all(
        80 <= len(record["description"]) <= 150
        and all(record.get(field) for field in ("name", "city", "description", "image_url"))
        for record in records
    )

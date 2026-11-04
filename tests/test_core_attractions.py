import json
from collections import Counter
from pathlib import Path


def test_core_dataset_has_twenty_complete_records_per_city():
    data_file = Path(__file__).parents[1] / "data" / "core_attractions.json"
    records = json.loads(data_file.read_text(encoding="utf-8"))
    counts = Counter(record["city"] for record in records)

    assert len(counts) >= 6
    assert set(counts.values()) == {20}
    assert all(
        80 <= len(record["description"]) <= 150
        and all(record.get(field) for field in ("name", "city", "description", "image_url"))
        for record in records
    )

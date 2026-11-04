from collections import Counter

from data.core_attractions import build_core_attractions


def test_core_dataset_has_twenty_complete_records_per_city():
    records = build_core_attractions()
    counts = Counter(record["city"] for record in records)

    assert len(records) == 120
    assert set(counts.values()) == {20}
    assert all(
        80 <= len(record["description"]) <= 150
        and all(record.get(field) for field in ("name", "city", "description", "image_url"))
        for record in records
    )

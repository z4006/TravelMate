from database.attractions import migrate_attractions
from database.connection import db_transaction, get_db
from scripts.import_osm_attractions import import_elements


def test_osm_import_is_idempotent(app):
    elements = [
        {
            "type": "node",
            "id": 123,
            "lat": 39.9,
            "lon": 116.4,
            "tags": {
                "name": "测试博物馆",
                "tourism": "museum",
                "addr:city": "北京市",
                "description": "测试说明",
            },
        }
    ]
    with app.app_context():
        with db_transaction() as database:
            migrate_attractions(database)
            database.execute(
                "INSERT OR IGNORE INTO attraction_categories (name, slug) "
                "VALUES (?, ?)",
                ("历史古迹", "historical"),
            )
            first = import_elements(database, elements)
            second = import_elements(database, elements)
        row = get_db().execute(
            "SELECT source, source_id, latitude, longitude FROM attractions "
            "WHERE source_id = ?",
            ("node/123",),
        ).fetchone()
    assert first == (1, 0)
    assert second == (0, 1)
    assert dict(row) == {
        "source": "openstreetmap",
        "source_id": "node/123",
        "latitude": 39.9,
        "longitude": 116.4,
    }

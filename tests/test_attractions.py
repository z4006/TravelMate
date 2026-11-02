"""景点模块临时数据库测试。"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest
from flask import Flask


FEATURE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = next(
    (
        parent
        for parent in (FEATURE_ROOT, *FEATURE_ROOT.parents)
        if (parent / "database" / "connection.py").is_file()
    ),
    Path(os.environ.get("TRAVELMATE_PROJECT_ROOT", Path.home() / "work" / "TravelMate")),
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


attraction_data = _load_module(
    "database.attractions",
    FEATURE_ROOT / "database" / "attractions.py",
)
attraction_routes = _load_module(
    "travelmate_feature_attraction_routes",
    FEATURE_ROOT / "routes" / "attractions.py",
)
from database.connection import close_db, db_transaction, get_db  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    app = Flask(__name__)
    app.config.update(
        DATABASE=str(tmp_path / "attractions-test.db"),
        TESTING=True,
    )
    app.register_blueprint(attraction_routes.attractions_bp)
    app.teardown_appcontext(close_db)
    with app.app_context():
        with db_transaction() as database:
            attraction_data.migrate_attractions(database)
            attraction_data.seed_initial_attractions(database)
    return app.test_client()


def test_list_supports_pagination_and_filters(client):
    response = client.get(
        "/api/attractions?page=1&page_size=1&category=historical&city=北京市"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload) == {"success", "message", "data"}
    assert payload["success"] is True
    assert payload["data"]["total"] == 2
    assert payload["data"]["page_size"] == 1
    assert len(payload["data"]["items"]) == 1
    assert payload["data"]["items"][0]["category"]["slug"] == "historical"
    assert payload["data"]["items"][0]["created_at"].endswith("+00:00")


def test_keyword_treats_like_wildcards_as_literals(client):
    assert client.get("/api/attractions?q=%25").get_json()["data"]["total"] == 0
    assert client.get("/api/attractions?q=西湖").get_json()["data"]["total"] == 1


def test_keyword_alias_matches_frontend_parameter(client):
    """页面使用 keyword 传参，接口需同时兼容 q 与 keyword。"""

    payload = client.get("/api/attractions?keyword=西湖").get_json()
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["name"] == "西湖"


def test_detail_categories_and_missing_attraction(client):
    categories = client.get("/api/attractions/categories")
    assert categories.status_code == 200
    assert len(categories.get_json()["data"]["items"]) == 3

    detail = client.get("/api/attractions/1")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["id"] == 1

    missing = client.get("/api/attractions/999")
    assert missing.status_code == 404
    assert missing.get_json()["data"] is None


def test_invalid_pagination_and_inactive_detail(client):
    invalid = client.get("/api/attractions?page=0")
    assert invalid.status_code == 400

    with client.application.app_context():
        with db_transaction() as database:
            database.execute(
                "UPDATE attractions SET status = ? WHERE slug = ?",
                ("inactive", "west-lake"),
            )
        row = get_db().execute(
            "SELECT id FROM attractions WHERE slug = ?",
            ("west-lake",),
        ).fetchone()
    hidden = client.get(f"/api/attractions/{row['id']}")
    assert hidden.status_code == 404


def test_migration_and_seed_are_idempotent(client):
    with client.application.app_context():
        with db_transaction() as database:
            attraction_data.migrate_attractions(database)
            attraction_data.seed_initial_attractions(database)
        assert get_db().execute(
            "SELECT COUNT(*) FROM attractions"
        ).fetchone()[0] == 5


def test_attractions_id_supports_itinerary_foreign_key(client):
    with client.application.app_context():
        database = get_db()
        columns = database.execute("PRAGMA table_info(attractions)").fetchall()
        assert any(column["name"] == "id" and column["pk"] == 1 for column in columns)

        database.execute(
            "CREATE TABLE itinerary_attractions ("
            "attraction_id INTEGER NOT NULL REFERENCES attractions(id))"
        )
        attraction_id = database.execute(
            "SELECT id FROM attractions ORDER BY id LIMIT 1"
        ).fetchone()["id"]
        database.execute(
            "INSERT INTO itinerary_attractions (attraction_id) VALUES (?)",
            (attraction_id,),
        )

"""收藏和行程接口测试。"""

from database.attractions import migrate_attractions, seed_initial_attractions
from database.connection import db_transaction, get_db


def register_and_login(client, headers, username="zhangsan"):
    client.post(
        "/api/register",
        json={
            "username": username,
            "password": "Password123",
            "email": "test@example.com",
        },
        headers=headers,
    )
    response = client.post(
        "/api/login",
        json={"username": username, "password": "Password123"},
        headers=headers,
    )
    assert response.status_code == 200
    headers["X-CSRF-Token"] = client.get(
        "/api/csrf-token"
    ).get_json()["data"]["csrf_token"]


def add_attractions(app):
    """灌入核心景点，并返回一个真实存在的景点 ID。

    重建核心数据后自增主键会变化，测试不能假设 ID 一定是 1。
    """

    with app.app_context():
        database = get_db()
        with db_transaction():
            migrate_attractions(database)
            seed_initial_attractions(database)
        row = database.execute(
            "SELECT id FROM attractions ORDER BY id LIMIT 1"
        ).fetchone()
        assert row is not None, "景点数据为空，测试无法继续"
        return row[0]


def test_favorite_requires_login(client):
    response = client.get("/api/favorites")

    assert response.status_code == 401


def test_create_list_and_remove_favorite(app, client, csrf_headers):
    attraction_id = add_attractions(app)
    register_and_login(client, csrf_headers)

    response = client.post(
        "/api/favorites", json={"attraction_id": attraction_id}, headers=csrf_headers
    )
    assert response.status_code == 201
    assert (
        client.get("/api/favorites").get_json()["data"][0]["attraction_id"]
        == attraction_id
    )

    response = client.post(
        "/api/favorites", json={"attraction_id": attraction_id}, headers=csrf_headers
    )
    assert response.status_code == 409

    response = client.delete(
        f"/api/favorites/{attraction_id}", headers=csrf_headers
    )
    assert response.status_code == 200


def test_itinerary_crud_and_ownership(app, client, csrf_headers):
    attraction_id = add_attractions(app)
    register_and_login(client, csrf_headers)
    payload = {
        "title": "杭州之旅",
        "start_date": "2026-11-10",
        "end_date": "2026-11-12",
        "notes": "慢游",
        "attractions": [{"attraction_id": attraction_id, "visit_date": "2026-11-10"}],
    }

    response = client.post(
        "/api/itineraries", json=payload, headers=csrf_headers
    )
    assert response.status_code == 201
    itinerary_id = response.get_json()["data"]["id"]
    assert client.get(f"/api/itineraries/{itinerary_id}").status_code == 200

    response = client.put(
        f"/api/itineraries/{itinerary_id}",
        json={**payload, "title": "杭州三日游", "attractions": []},
        headers=csrf_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["title"] == "杭州三日游"

    response = client.delete(
        f"/api/itineraries/{itinerary_id}", headers=csrf_headers
    )
    assert response.status_code == 200
    assert client.get(f"/api/itineraries/{itinerary_id}").status_code == 404


def test_other_user_cannot_access_itinerary(app, client, csrf_headers):
    attraction_id = add_attractions(app)
    register_and_login(client, csrf_headers, username="alice")
    response = client.post(
        "/api/itineraries",
        json={"title": "私人行程", "attractions": [{"attraction_id": attraction_id}]},
        headers=csrf_headers,
    )
    itinerary_id = response.get_json()["data"]["id"]

    other = app.test_client()
    other_headers = {
        "X-CSRF-Token": other.get("/api/csrf-token").get_json()["data"]["csrf_token"]
    }
    register_and_login(other, other_headers, username="bob")

    assert other.get(f"/api/itineraries/{itinerary_id}").status_code == 404
    assert other.get("/api/favorites").get_json()["data"] == []


def test_invalid_itinerary_dates_are_rejected(app, client, csrf_headers):
    add_attractions(app)
    register_and_login(client, csrf_headers)

    response = client.post(
        "/api/itineraries",
        json={
            "title": "错误行程",
            "start_date": "2026-11-12",
            "end_date": "2026-11-10",
            "attractions": [],
        },
        headers=csrf_headers,
    )

    assert response.status_code == 400


def test_partial_update_preserves_omitted_fields(app, client, csrf_headers):
    attraction_id = add_attractions(app)
    register_and_login(client, csrf_headers)
    response = client.post(
        "/api/itineraries",
        json={
            "title": "原始行程",
            "start_date": "2026-11-10",
            "end_date": "2026-11-12",
            "notes": "保留",
            "attractions": [{"attraction_id": attraction_id}],
        },
        headers=csrf_headers,
    )
    itinerary_id = response.get_json()["data"]["id"]

    response = client.put(
        f"/api/itineraries/{itinerary_id}",
        json={"title": "新标题"},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["title"] == "新标题"
    assert data["start_date"] == "2026-11-10"
    assert data["attractions"][0]["attraction_id"] == attraction_id

def test_itinerary_caption_generated_only_once(app, client, csrf_headers, monkeypatch):
    monkeypatch.setattr(
        "services.agent.ask_model",
        lambda *args, **kwargs: "🎒 两天把杭州逛明白了\n\n#杭州 #旅行",
    )
    attraction_id = add_attractions(app)
    register_and_login(client, csrf_headers)

    created = client.post(
        "/api/itineraries",
        json={"title": "杭州两日", "attractions": [{"attraction_id": attraction_id}]},
        headers=csrf_headers,
    ).get_json()["data"]

    first = client.post(
        f"/api/itineraries/{created['id']}/caption", json={}, headers=csrf_headers
    )
    assert first.status_code == 200
    caption = first.get_json()["data"]["caption"]
    assert caption

    second = client.post(
        f"/api/itineraries/{created['id']}/caption", json={}, headers=csrf_headers
    )
    assert second.status_code == 409
    assert second.get_json()["data"]["caption"] == caption

    listed = client.get("/api/itineraries").get_json()["data"]
    assert listed[0]["caption"] == caption


def test_itinerary_caption_requires_attractions(app, client, csrf_headers, monkeypatch):
    monkeypatch.setattr("services.agent.ask_model", lambda *args, **kwargs: "x")
    add_attractions(app)
    register_and_login(client, csrf_headers)

    created = client.post(
        "/api/itineraries",
        json={"title": "空行程", "attractions": []},
        headers=csrf_headers,
    ).get_json()["data"]

    response = client.post(
        f"/api/itineraries/{created['id']}/caption", json={}, headers=csrf_headers
    )
    assert response.status_code == 400

"""收藏和行程接口测试。"""

from database.connection import db_transaction, get_db


def register_and_login(client, headers):
    client.post(
        "/api/register",
        json={
            "username": "zhangsan",
            "password": "Password123",
            "email": "test@example.com",
        },
        headers=headers,
    )
    response = client.post(
        "/api/login",
        json={"username": "zhangsan", "password": "Password123"},
        headers=headers,
    )
    assert response.status_code == 200
    headers["X-CSRF-Token"] = client.get(
        "/api/csrf-token"
    ).get_json()["data"]["csrf_token"]


def add_attractions(app):
    with app.app_context():
        with db_transaction():
            get_db().execute(
                "CREATE TABLE attractions ("
                "id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT)"
            )
            get_db().executemany(
                "INSERT INTO attractions (id, name, city) VALUES (?, ?, ?)",
                [(1, "西湖", "杭州"), (2, "故宫", "北京")],
            )


def test_favorite_requires_login(client):
    response = client.get("/api/favorites")

    assert response.status_code == 401


def test_create_list_and_remove_favorite(app, client, csrf_headers):
    add_attractions(app)
    register_and_login(client, csrf_headers)

    response = client.post(
        "/api/favorites", json={"attraction_id": 1}, headers=csrf_headers
    )
    assert response.status_code == 201
    assert client.get("/api/favorites").get_json()["data"][0]["attraction_id"] == 1

    response = client.post(
        "/api/favorites", json={"attraction_id": 1}, headers=csrf_headers
    )
    assert response.status_code == 409

    response = client.delete("/api/favorites/1", headers=csrf_headers)
    assert response.status_code == 200


def test_itinerary_crud_and_ownership(app, client, csrf_headers):
    add_attractions(app)
    register_and_login(client, csrf_headers)
    payload = {
        "title": "杭州之旅",
        "start_date": "2026-11-10",
        "end_date": "2026-11-12",
        "notes": "慢游",
        "attractions": [{"attraction_id": 1, "visit_date": "2026-11-10"}],
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

"""AI 助手接口测试（不调用真实模型）。"""

import json

import pytest

from database.attractions import migrate_attractions, seed_initial_attractions
from database.connection import db_transaction, get_db


def prepare(app):
    with app.app_context():
        with db_transaction():
            database = get_db()
            migrate_attractions(database)
            seed_initial_attractions(database)


def register_and_login(client, headers):
    client.post(
        "/api/register",
        json={"username": "agentuser", "password": "Password123"},
        headers=headers,
    )
    response = client.post(
        "/api/login",
        json={"username": "agentuser", "password": "Password123"},
        headers=headers,
    )
    assert response.status_code == 200
    headers["X-CSRF-Token"] = client.get(
        "/api/csrf-token"
    ).get_json()["data"]["csrf_token"]


def test_agent_status_is_public(client):
    assert client.get("/api/agent/status").status_code == 200


def test_guest_can_chat_and_plan_but_not_save(app, client, csrf_headers, monkeypatch):
    monkeypatch.setattr(
        "services.agent.settings",
        lambda: {"api_key": "", "model": "", "base_url": ""},
    )
    prepare(app)

    chat = client.post(
        "/api/agent/chat", json={"message": "西湖门票多少"}, headers=csrf_headers
    )
    assert chat.status_code == 200

    plan = client.post(
        "/api/agent/plan", json={"message": "杭州两天"}, headers=csrf_headers
    )
    assert plan.status_code == 200

    save = client.post(
        "/api/agent/plan",
        json={"message": "杭州两天", "save": True},
        headers=csrf_headers,
    )
    assert save.status_code == 401


def test_agent_write_requires_csrf(client):
    assert client.post("/api/agent/chat", json={"message": "hi"}).status_code == 403


def test_plan_falls_back_to_rules_without_model(app, client, csrf_headers, monkeypatch):
    monkeypatch.setattr(
        "services.agent.settings",
        lambda: {"api_key": "", "model": "", "base_url": ""},
    )
    prepare(app)
    register_and_login(client, csrf_headers)

    response = client.post(
        "/api/agent/plan",
        json={"message": "想去杭州玩两天", "days": 2},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["source"] == "rule"
    assert 1 <= len(data["plan"]["days"]) <= 2
    assert data["itinerary_payload"]["attractions"]


def test_plan_drops_unknown_attraction_ids(app, client, csrf_headers, monkeypatch):
    fake = json.dumps(
        {
            "title": "模型生成的行程",
            "summary": "测试",
            "days": [
                {"day": 1, "items": [
                    {"attraction_id": 1, "note": "上午"},
                    {"attraction_id": 999999, "note": "不存在的景点"},
                ]}
            ],
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr("services.agent.ask_model", lambda *a, **k: fake)
    prepare(app)
    register_and_login(client, csrf_headers)

    response = client.post(
        "/api/agent/plan",
        json={"message": "随便安排一下"},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["source"] == "model"
    ids = [item["attraction_id"] for item in data["plan"]["days"][0]["items"]]
    assert 1 in ids
    assert 999999 not in ids


def test_plan_can_save_itinerary(app, client, csrf_headers, monkeypatch):
    monkeypatch.setattr(
        "services.agent.settings",
        lambda: {"api_key": "", "model": "", "base_url": ""},
    )
    prepare(app)
    register_and_login(client, csrf_headers)

    response = client.post(
        "/api/agent/plan",
        json={"message": "西安两天", "days": 2, "save": True},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    saved = response.get_json()["data"]["saved"]
    assert saved is not None
    listed = client.get("/api/itineraries").get_json()["data"]
    assert any(item["id"] == saved["id"] for item in listed)


def test_plan_rejects_bad_parameters(app, client, csrf_headers):
    prepare(app)
    register_and_login(client, csrf_headers)

    assert client.post(
        "/api/agent/plan", json={"message": ""}, headers=csrf_headers
    ).status_code == 400
    assert client.post(
        "/api/agent/plan", json={"message": "x", "days": 99}, headers=csrf_headers
    ).status_code == 400
    assert client.post(
        "/api/agent/plan", json={"message": "x", "days": True}, headers=csrf_headers
    ).status_code == 400


def test_chat_falls_back_without_model(app, client, csrf_headers, monkeypatch):
    monkeypatch.setattr(
        "services.agent.settings",
        lambda: {"api_key": "", "model": "", "base_url": ""},
    )
    prepare(app)
    register_and_login(client, csrf_headers)

    response = client.post(
        "/api/agent/chat",
        json={"message": "西湖要门票吗？", "history": []},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["reply"]
    assert data["source"] == "rule"

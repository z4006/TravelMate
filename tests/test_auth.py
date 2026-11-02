"""用户认证接口测试。"""

from database.connection import get_db


def register(client, headers, **values):
    payload = {
        "username": "zhangsan",
        "password": "Password123",
        "email": "test@example.com",
    }
    payload.update(values)
    return client.post("/api/register", json=payload, headers=headers)


def login(client, headers, **values):
    payload = {"username": "zhangsan", "password": "Password123"}
    payload.update(values)
    response = client.post("/api/login", json=payload, headers=headers)
    if response.status_code == 200:
        headers["X-CSRF-Token"] = client.get(
            "/api/csrf-token"
        ).get_json()["data"]["csrf_token"]
    return response


def test_register_success(client, csrf_headers):
    response = register(client, csrf_headers)

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["username"] == "zhangsan"
    assert "password_hash" not in data


def test_duplicate_username_registration(client, csrf_headers):
    register(client, csrf_headers)

    response = register(client, csrf_headers)

    assert response.status_code == 409
    assert response.get_json()["success"] is False


def test_weak_password_registration(client, csrf_headers):
    response = register(client, csrf_headers, password="12345678")

    assert response.status_code == 400


def test_blank_nickname_is_rejected(client, csrf_headers):
    response = register(client, csrf_headers, nickname="   ")

    assert response.status_code == 400


def test_username_case_is_normalized(client, csrf_headers):
    assert register(client, csrf_headers, username="ZhangSan").status_code == 201
    response = register(client, csrf_headers, username="zhangsan")

    assert response.status_code == 409


def test_login_is_rate_limited_after_repeated_failures(client, csrf_headers):
    register(client, csrf_headers)
    for _ in range(5):
        assert login(client, csrf_headers, password="Wrong123").status_code == 401

    assert login(client, csrf_headers, password="Wrong123").status_code == 429


def test_login_with_correct_password(client, csrf_headers):
    register(client, csrf_headers)

    response = login(client, csrf_headers)

    assert response.status_code == 200
    assert response.get_json()["data"]["username"] == "zhangsan"


def test_login_with_wrong_password(client, csrf_headers):
    register(client, csrf_headers)

    response = login(client, csrf_headers, password="Wrong123")

    assert response.status_code == 401
    assert response.get_json()["message"] == "用户名或密码错误"


def test_login_with_unknown_user(client, csrf_headers):
    response = login(client, csrf_headers)

    assert response.status_code == 401


def test_unauthenticated_user_info(client):
    response = client.get("/api/user/info")

    assert response.status_code == 401


def test_authenticated_user_info(client, csrf_headers):
    register(client, csrf_headers)
    login(client, csrf_headers)

    response = client.get("/api/user/info")

    assert response.status_code == 200
    assert response.get_json()["data"]["username"] == "zhangsan"


def test_logout(client, csrf_headers):
    register(client, csrf_headers)
    login(client, csrf_headers)

    response = client.post("/api/logout", headers=csrf_headers)

    assert response.status_code == 200
    assert client.get("/api/user/info").status_code == 401


def test_update_profile(client, csrf_headers):
    register(client, csrf_headers)
    login(client, csrf_headers)

    response = client.put(
        "/api/user/profile",
        json={"nickname": "张三", "email": "new@example.com"},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["nickname"] == "张三"


def test_wrong_old_password_cannot_change_password(client, csrf_headers):
    register(client, csrf_headers)
    login(client, csrf_headers)

    response = client.put(
        "/api/user/password",
        json={"old_password": "Wrong123", "new_password": "NewPassword123"},
        headers=csrf_headers,
    )

    assert response.status_code == 401


def test_regular_user_cannot_change_role(client, csrf_headers):
    register(client, csrf_headers)
    login(client, csrf_headers)

    response = client.put(
        "/api/user/profile",
        json={"nickname": "管理员", "role": "admin"},
        headers=csrf_headers,
    )

    assert response.status_code == 400
    assert client.get("/api/user/info").get_json()["data"]["role"] == "user"


def test_password_is_not_stored_as_plaintext(app, client, csrf_headers):
    register(client, csrf_headers)

    with app.app_context():
        row = get_db().execute(
            "SELECT password_hash FROM users WHERE username = ?",
            ("zhangsan",),
        ).fetchone()

    assert row["password_hash"] != "Password123"
    assert row["password_hash"].startswith("scrypt:")


def test_password_change_invalidates_old_session(app, client, csrf_headers):
    register(client, csrf_headers)
    login(client, csrf_headers)
    with client.session_transaction() as session:
        old_version = session["session_version"]

    response = client.put(
        "/api/user/password",
        json={"old_password": "Password123", "new_password": "NewPassword123"},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session["session_version"] != old_version


def test_password_change_invalidates_other_sessions(app, client, csrf_headers):
    register(client, csrf_headers)
    login(client, csrf_headers)

    other_client = app.test_client()
    other_csrf_response = other_client.get("/api/csrf-token")
    other_headers = {
        "X-CSRF-Token": other_csrf_response.get_json()["data"]["csrf_token"]
    }
    login_response = login(other_client, other_headers)
    assert login_response.status_code == 200

    response = client.put(
        "/api/user/password",
        json={"old_password": "Password123", "new_password": "NewPassword123"},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    assert other_client.get("/api/user/info").status_code == 401

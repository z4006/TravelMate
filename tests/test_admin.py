"""管理员用户管理接口测试。"""

from database.connection import get_db


def register(client, headers, username, password="Password123"):
    return client.post(
        "/api/register",
        json={
            "username": username,
            "password": password,
            "email": f"{username}@example.com",
        },
        headers=headers,
    )


def csrf_headers(client):
    response = client.get("/api/csrf-token")
    return {"X-CSRF-Token": response.get_json()["data"]["csrf_token"]}


def login(client, headers, username, password="Password123"):
    response = client.post(
        "/api/login",
        json={"username": username, "password": password},
        headers=headers,
    )
    if response.status_code == 200:
        headers["X-CSRF-Token"] = client.get(
            "/api/csrf-token"
        ).get_json()["data"]["csrf_token"]
    return response


def create_user(client, username):
    headers = csrf_headers(client)
    response = register(client, headers, username)
    assert response.status_code == 201
    return response.get_json()["data"]["id"]


def promote_to_admin(app, username):
    with app.app_context():
        database = get_db()
        database.execute(
            "UPDATE users SET role = 'admin' WHERE username = ?",
            (username,),
        )
        database.commit()


def admin_client(app):
    client = app.test_client()
    headers = csrf_headers(client)
    register(client, headers, "adminuser")
    promote_to_admin(app, "adminuser")
    assert login(client, headers, "adminuser").status_code == 200
    return client, headers


def test_unauthenticated_admin_access(client):
    response = client.get("/api/admin/users")

    assert response.status_code == 401


def test_regular_user_cannot_access_admin_api(client):
    headers = csrf_headers(client)
    register(client, headers, "normaluser")
    assert login(client, headers, "normaluser").status_code == 200

    response = client.get("/api/admin/users")

    assert response.status_code == 403


def test_admin_can_list_users(app, client):
    admin, _ = admin_client(app)
    create_user(client, "normaluser")

    response = admin.get("/api/admin/users")

    assert response.status_code == 200
    usernames = {item["username"] for item in response.get_json()["data"]["items"]}
    assert {"adminuser", "normaluser"} <= usernames
    assert all("password_hash" not in item for item in response.get_json()["data"]["items"])


def test_admin_can_search_users(app):
    admin, _ = admin_client(app)
    create_user(admin, "searchtarget")
    create_user(admin, "otheruser")

    response = admin.get("/api/admin/users?search=searchtarget")

    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert [item["username"] for item in items] == ["searchtarget"]


def test_admin_search_treats_wildcards_as_literals(app):
    admin, _ = admin_client(app)
    create_user(admin, "plainuser")
    create_user(admin, "anotheruser")

    response = admin.get("/api/admin/users?search=%25")

    assert response.status_code == 200
    assert response.get_json()["data"]["items"] == []


def test_admin_can_disable_user_and_audit_is_written(app):
    admin, _ = admin_client(app)
    target_id = create_user(admin, "targetuser")
    headers = csrf_headers(admin)

    response = admin.patch(
        f"/api/admin/users/{target_id}/status",
        json={"status": "disabled"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "disabled"
    with app.app_context():
        log = get_db().execute(
            "SELECT action, target_user_id FROM audit_logs "
            "WHERE target_user_id = ? ORDER BY id DESC",
            (target_id,),
        ).fetchone()
    assert log["action"] == "user_status_changed"


def test_disabled_user_cannot_login(app, client):
    target_id = create_user(client, "disableduser")
    with app.app_context():
        database = get_db()
        database.execute(
            "UPDATE users SET status = 'disabled' WHERE id = ?",
            (target_id,),
        )
        database.commit()
    headers = csrf_headers(client)

    response = login(client, headers, "disableduser")

    assert response.status_code == 401


def test_regular_user_cannot_change_other_user_status(client):
    headers = csrf_headers(client)
    target_id = create_user(client, "targetuser")
    register(client, headers, "normaluser")
    assert login(client, headers, "normaluser").status_code == 200
    headers = csrf_headers(client)

    response = client.patch(
        f"/api/admin/users/{target_id}/status",
        json={"status": "disabled"},
        headers=headers,
    )

    assert response.status_code == 403


def test_admin_cannot_disable_admin_account(app):
    admin, _ = admin_client(app)
    with app.app_context():
        admin_id = get_db().execute(
            "SELECT id FROM users WHERE username = 'adminuser'"
        ).fetchone()["id"]
    headers = csrf_headers(admin)

    response = admin.patch(
        f"/api/admin/users/{admin_id}/status",
        json={"status": "disabled"},
        headers=headers,
    )

    assert response.status_code == 403


def test_disabled_existing_session_is_rejected(app):
    admin, _ = admin_client(app)
    target_id = create_user(admin, "onlineuser")
    target_headers = csrf_headers(admin)
    assert login(admin, target_headers, "onlineuser").status_code == 200

    with app.app_context():
        database = get_db()
        database.execute(
            "UPDATE users SET status = 'disabled' WHERE id = ?",
            (target_id,),
        )
        database.commit()

    assert admin.get("/api/user/info").status_code == 401

"""基础设施回归测试。"""

from pathlib import Path

from app import create_app
from database.connection import get_db, init_db


def test_create_app_without_database_initialization_has_no_database_side_effect(
    tmp_path,
    monkeypatch,
):
    default_database = Path(__file__).parents[1] / "database" / "travelmate.db"
    before = default_database.stat().st_mtime_ns if default_database.exists() else None
    monkeypatch.delenv("TRAVELMATE_DATABASE", raising=False)

    create_app("development", init_database=False)

    after = default_database.stat().st_mtime_ns if default_database.exists() else None
    assert after == before


def test_database_initialization_is_idempotent(tmp_path):
    app = create_app(
        "testing",
        overrides={"DATABASE": str(tmp_path / "idempotent.db")},
        init_database=False,
    )
    init_db(app)
    init_db(app)

    with app.app_context():
        assert get_db().execute(
            "SELECT name FROM sqlite_master WHERE name = 'users'"
        ).fetchone()


def test_timestamps_use_utc_iso_format(app, client, csrf_headers):
    response = client.post(
        "/api/register",
        json={"username": "timeuser", "password": "Password123"},
        headers=csrf_headers,
    )
    assert response.status_code == 201
    with app.app_context():
        created_at = get_db().execute(
            "SELECT created_at FROM users WHERE username_key = ?",
            ("timeuser",),
        ).fetchone()["created_at"]
    assert " " not in created_at
    assert created_at.endswith("+00:00")

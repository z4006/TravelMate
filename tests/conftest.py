"""认证接口测试夹具。"""

import pytest

from app import create_app
from database.connection import init_db


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        "testing",
        overrides={
            "DATABASE": str(tmp_path / "test.db"),
            "TESTING": True,
        },
    )
    init_db(application)
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_headers(client):
    response = client.get("/api/csrf-token")
    token = response.get_json()["data"]["csrf_token"]
    return {"X-CSRF-Token": token}

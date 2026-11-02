"""TravelMate Flask 应用入口。"""

import os
from typing import Any, Type

from flask import Flask, jsonify

from config import CONFIG_BY_NAME, ProductionConfig
from database.connection import close_db, init_db


def create_app(
    config_name: str | None = None,
    overrides: dict[str, Any] | None = None,
    init_database: bool = True,
) -> Flask:
    """创建并配置 Flask 应用实例。"""

    selected_config = config_name or os.getenv(
        "TRAVELMATE_ENV",
        "development",
    )
    config_class: Type = CONFIG_BY_NAME.get(
        selected_config,
        CONFIG_BY_NAME["development"],
    )

    if config_class is ProductionConfig:
        config_class.validate()

    app = Flask(__name__)
    app.config.from_object(config_class)
    if overrides:
        app.config.update(overrides)
    app.json.ensure_ascii = False

    from routes.base import base_bp
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.itinerary import itinerary_bp

    app.register_blueprint(base_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(itinerary_bp)
    app.teardown_appcontext(close_db)
    if init_database:
        init_db(app)
    else:
        @app.before_request
        def ensure_database_initialized():
            init_db(app)
    register_error_handlers(app)
    register_security_headers(app)
    return app


def register_error_handlers(app: Flask) -> None:
    """统一处理常见 HTTP 错误并返回 JSON。"""

    @app.errorhandler(404)
    def handle_not_found(_error: Exception):
        del _error
        return (
            jsonify(
                success=False,
                message="请求的资源不存在",
                data=None,
            ),
            404,
        )

    @app.errorhandler(405)
    def handle_method_not_allowed(_error: Exception):
        del _error
        return (
            jsonify(
                success=False,
                message="请求方法不被允许",
                data=None,
            ),
            405,
        )

    @app.errorhandler(500)
    def handle_internal_server_error(_error: Exception):
        del _error
        return (
            jsonify(
                success=False,
                message="服务器内部错误",
                data=None,
            ),
            500,
        )

    @app.errorhandler(400)
    def handle_bad_request(_error: Exception):
        del _error
        return jsonify(success=False, message="请求参数错误", data=None), 400

    @app.errorhandler(403)
    def handle_forbidden(_error: Exception):
        del _error
        return jsonify(success=False, message="没有访问权限", data=None), 403

    @app.errorhandler(429)
    def handle_too_many_requests(_error: Exception):
        del _error
        return jsonify(success=False, message="请求过于频繁，请稍后再试", data=None), 429


def register_security_headers(app: Flask) -> None:
    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response


app = create_app(init_database=False)


if __name__ == "__main__":
    init_db(app)
    app.run()
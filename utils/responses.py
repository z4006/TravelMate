"""统一 API 响应和请求体工具。"""

from typing import Any

from flask import jsonify, request


def api_response(
    success: bool,
    message: str,
    data: dict[str, Any] | None = None,
    status_code: int = 200,
):
    return jsonify(success=success, message=message, data=data), status_code


def request_data() -> dict[str, Any] | None:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else None

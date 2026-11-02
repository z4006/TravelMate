"""基础系统路由。"""

from flask import Blueprint, jsonify


base_bp = Blueprint("base", __name__)


@base_bp.get("/")
def index():
    """返回服务状态，作为基础首页接口。"""

    return jsonify(
        success=True,
        message="TravelMate 服务运行正常",
        data={"service": "TravelMate"},
    )

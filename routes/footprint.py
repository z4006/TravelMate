"""旅行足迹 API（任务 C）。

GET /api/footprint 返回当前登录用户的足迹聚合数据：
- cities：已打卡城市（来自收藏 + 行程），带经纬度与统计；
- background：全部有景点的城市，作为地图底色；
- stats / level：统计数字与旅行等级。

页面模板由 routes/pages.py 的 /footprint 提供，这里只输出 JSON。
"""

from flask import Blueprint, g

from database.connection import get_db
from services.footprint import build_footprint
from utils.decorators import login_required
from utils.responses import api_response

footprint_bp = Blueprint("footprint", __name__)


@footprint_bp.get("/api/footprint")
@login_required
def footprint():
    data = build_footprint(get_db(), g.current_user["id"])
    return api_response(True, "操作成功", data)

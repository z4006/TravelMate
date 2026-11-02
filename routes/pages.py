"""前端页面路由（成员 B）。

本模块只负责渲染 templates/ 下的页面骨架，页面数据全部由浏览器通过
/api/* 接口获取，这里不直接访问数据库、不重复实现任何业务逻辑。

接入方式（需要成员 A 确认后执行，共两处）：
1. app.py 中注册本 Blueprint：

       from routes.pages import pages_bp
       app.register_blueprint(pages_bp)

2. routes/base.py 的 "/" 目前返回服务状态 JSON，会先匹配到首页地址。
   建议把它改成 "/api/health"，把 "/" 留给页面路由。
"""

from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def index():
    """旅游网站首页。"""

    return render_template(
        "index.html",
        active_page="home",
        page_title="TravelMate 旅游信息与行程规划",
    )


@pages_bp.get("/login")
def login():
    """用户登录页面。"""

    return render_template(
        "login.html",
        active_page="login",
        page_title="登录 - TravelMate",
    )


@pages_bp.get("/register")
def register():
    """用户注册页面。"""

    return render_template(
        "register.html",
        active_page="register",
        page_title="注册 - TravelMate",
    )


@pages_bp.get("/attractions")
def attractions():
    """景点列表页面，支持 ?city= 与 ?keyword= 查询参数。"""

    return render_template(
        "attractions.html",
        active_page="attractions",
        page_title="景点列表 - TravelMate",
    )


@pages_bp.get("/attractions/<int:attraction_id>")
def attraction_detail(attraction_id: int):
    """景点详情页面，数据由 /api/attractions/<id> 提供。"""

    return render_template(
        "attraction_detail.html",
        active_page="attractions",
        page_title="景点详情 - TravelMate",
        attraction_id=attraction_id,
    )

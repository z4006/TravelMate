# 成员 B 前端开发说明

> 对应分支：`feature/frontend`（基于成员 A 的 `feature/user-auth` 提交 `fc0cf06`）

## 1. 完成了哪些功能

| 页面 | 地址 | 文件 | 说明 |
| --- | --- | --- | --- |
| 首页 | `/` | `templates/index.html` + `static/js/home.js` | Hero 搜索、热门城市入口、热门景点卡片（取前 6 条） |
| 登录 | `/login` | `templates/login.html` + `static/js/auth.js` | 前端校验、错误提示、登录成功跳转（支持 `?next=`） |
| 注册 | `/register` | `templates/register.html` + `static/js/auth.js` | 用户名/昵称/邮箱/密码/确认密码校验，成功后跳转登录页并回填用户名 |
| 景点列表 | `/attractions` | `templates/attractions.html` + `static/js/attractions.js` | `?city=`、`?keyword=` 筛选、结果计数、空状态、加载失败重试 |
| 景点详情 | `/attractions/<id>` | `templates/attraction_detail.html` + `static/js/detail.js` | 名称、城市、标签、简介、开放时间、门票、地址、电话 |

公共部分：`templates/base.html`、`templates/partials/navbar.html`、`templates/partials/footer.html`，
样式 `static/css/base.css`、`static/css/pages.css`、`static/css/responsive.css`，
图标与占位图 `static/images/logo.svg`、`static/images/placeholder-attraction.svg`。

## 2. 新增和修改了哪些文件

新增（均属于成员 B 的前端范围）：

```text
templates/base.html
templates/index.html
templates/login.html
templates/register.html
templates/attractions.html
templates/attraction_detail.html
templates/partials/navbar.html
templates/partials/footer.html
static/css/base.css
static/css/pages.css
static/css/responsive.css
static/js/api.js
static/js/ui.js
static/js/nav.js
static/js/auth.js
static/js/home.js
static/js/attractions.js
static/js/detail.js
static/images/logo.svg
static/images/placeholder-attraction.svg
docs/member-b-frontend-guide.md
```

另外新增了一个页面路由模块 `routes/pages.py`，**需要成员 A 确认**（见第 6 节）。

没有修改：`app.py`、`config.py`、`database/connection.py`、`database/schema.sql`、
`database/users.py`、`routes/auth.py`、`routes/admin.py`、`routes/base.py`、`tests/`。

## 3. 依赖的后端接口（成员 A 已实现）

前端只调用接口，不重复实现注册登录后端：

| 用途 | 接口 | 前端读取的字段 |
| --- | --- | --- |
| 获取 CSRF Token | `GET /api/csrf-token` | `data.csrf_token` |
| 注册 | `POST /api/register`（`{username, password, email?, nickname?}`） | 201 + `data.username` |
| 登录 | `POST /api/login`（`{username, password}`） | 200 + `data.nickname` / `data.username` |
| 当前用户 | `GET /api/user/info` | `data.nickname`、`data.username`（导航栏） |
| 退出 | `POST /api/logout` | 200 |

景点相关（成员 C 负责，前端按兼容方式解析）：

| 用途 | 接口 | 前端兼容的字段名 |
| --- | --- | --- |
| 列表 | `GET /api/attractions`（可带 `city`、`keyword`） | `data` 为数组，或 `data.items / attractions / list / results / records / data` |
| 详情 | `GET /api/attractions/<id>` | `id/name/city/description/image_url/tags/open_time/ticket_price/address/phone/rating`，也兼容 `title/cover_url/summary/opening_hours/price` 等别名 |

## 4. Session Cookie 与 CSRF Token 处理

1. 页面加载后第一次写操作前，`static/js/api.js` 自动 `GET /api/csrf-token`，从 **`data.csrf_token`** 读取 Token。
2. 所有写操作（注册、登录、退出）都带 `X-CSRF-Token` 请求头，并统一 `credentials: 'same-origin'`，由浏览器自动携带 Session Cookie。
3. 后端在 `login` / `logout` 里执行 `session.clear()` 并重新生成 Token，因此**登录成功、退出成功后前端都会再次获取 Token**。
4. 若写操作返回 403 且 `message` 含 `CSRF`（说明后端在进入业务逻辑前就拒绝了请求），`api.js` 会刷新 Token 并**自动重试一次**，不会产生重复数据。
5. 401 由各页面自行处理（登录页提示密码错误，其余页面按未登录展示）。
6. 前端不保存密码、不写 `localStorage`/`sessionStorage`，不向服务端传 `user_id`、`role`、`status`；导航栏只把 `role` 之类的信息用于显示，权限判断仍由后端 `g.current_user` 决定。

## 5. 如何运行和测试

运行（需要先有成员 A 的后端代码，并完成第 6 节的注册步骤）：

```powershell
cd TravelMate
python app.py
# 浏览器访问 http://127.0.0.1:5000/
```

前端自检（在仓库外的临时目录执行，不产生任何提交）：

- `check_frontend.py`：页面渲染、静态资源、认证接口契约、景点接口数据链路，共 49 项（跑在**替身服务** `serve_pages.py` 上，该服务代替 A 注册了 `pages_bp` 并接管 `/`）。
- `check_integration.py`：**真实入口**检查，直接 `import app; app.create_app()`，不注入任何东西，断言 `pages.*` 在 `url_map`、`/login` 等返回 200 + HTML。**它是"`python app.py` 后页面可用"的唯一判据**。
- `e2e.test.mjs`（jsdom + 真实 Flask 服务，期望值来自接口数据，不写死景点名）：首页/列表/详情渲染、注册、登录、导航栏、退出、CSRF 失效重试，共 26 项。

一键跑：`powershell -ExecutionPolicy Bypass -File ..\_frontend_check\verify.ps1`（Node 需 `^22.22.2 || ^24.15.0 || >=26`，是 jsdom 30 的硬门槛）。

实测结果：`check_frontend.py` 49/49、`e2e.test.mjs` 26/26 通过；`node --check`、TypeScript 解析器、CSS 语言服务、pyright（`routes/pages.py`）均 0 诊断。
`check_integration.py` 当前 **失败**：`app.py` 未注册 `pages_bp`、`routes/base.py` 的 `/` 仍返回 JSON —— 这两处是第 6 节待 A 完成的接入动作，修好后该脚本自动转绿。
成员 A 的 `tests/` 未在本机运行（当前 Python 环境未安装 pytest，未在提交中声称测试通过）。

## 6. 需要成员 A 确认的两处公共文件改动

1. `app.py` 注册页面 Blueprint（新增 2 行）：

```python
from routes.pages import pages_bp   # 与其他 routes 一起导入
app.register_blueprint(pages_bp)
```

2. `routes/base.py` 的 `/` 目前返回服务状态 JSON，会先于页面路由匹配。建议改为 `/api/health`，
   把 `/` 留给首页；如果暂时不改，访问 `/` 会看到 JSON 而不是首页。

这两处都属于公共文件，**成员 B 没有改动**，等待 A 确认后由 A 修改或授权修改。

## 7. 已知问题与后续

- 景点接口（成员 C）尚未合并，页面已做好兜底：接口未就绪时显示"暂无景点数据 / 暂时无法加载景点"并可重试，不会报错白屏。
- 收藏、行程规划页面属于成员 D，本次未涉及，导航栏暂未放置对应入口。
- 图片依赖接口返回的 `image_url`；无图片或加载失败时自动回落到本地占位图，不依赖外网资源。

# TravelMate

## 本地运行

```powershell
cd C:\Users\曾\Desktop\WorkSpace\TravelMate
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

开发环境默认使用本地配置。正式环境启动前必须设置密钥：

```powershell
$env:TRAVELMATE_ENV="production"
$env:TRAVELMATE_SECRET_KEY="请设置正式环境密钥"
.venv\Scripts\python.exe app.py
```

## 用户认证接口

写操作需要先调用 `GET /api/csrf-token`，再把返回的 `csrf_token` 放入
`X-CSRF-Token` 请求头。

服务和页面入口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | 网站首页 |
| GET | `/login` | 登录页面 |
| GET | `/register` | 注册页面 |
| GET | `/attractions` | 景点列表页面 |
| GET | `/api/health` | JSON 服务健康检查 |

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/csrf-token` | 获取 CSRF token |
| POST | `/api/register` | 注册普通用户 |
| POST | `/api/login` | 登录并创建 Session |
| POST | `/api/logout` | 清除当前 Session |
| GET | `/api/user/info` | 获取当前用户信息 |
| PUT | `/api/user/profile` | 修改昵称和邮箱 |
| PUT | `/api/user/password` | 修改密码并使其他会话失效 |
| GET | `/api/admin/users` | 管理员分页查询用户 |
| GET | `/api/admin/users/<user_id>` | 管理员查看用户资料 |
| PATCH | `/api/admin/users/<user_id>/status` | 管理员启用或禁用普通用户 |

所有接口都返回 `success`、`message` 和 `data` 三个字段。密码使用
Werkzeug 哈希保存，不会通过接口返回。

用户认证和管理员路由分别依赖公共的 `utils` 工具层；数据库写操作由
`db_transaction()` 统一提交或回滚，避免业务模块互相提交半成品事务。
测试应用通过 `create_app(..., overrides={"DATABASE": ...})` 注入临时数据库，
不会初始化或污染 `database/travelmate.db`。

数据库初始化会自动创建用户、景点、收藏和行程所需的数据表，但不会自动写入
演示景点数据。若需要本地演示数据，可以执行：

```powershell
.venv\Scripts\python.exe -m scripts.seed_attractions
```

运行测试：

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## 管理员初始化

系统不会自动创建硬编码管理员或固定密码。先通过注册接口创建普通用户，
再运行一次性交互式初始化命令，输入该已有用户的用户名和密码：

```powershell
.venv\Scripts\python.exe -m scripts.create_admin
```

命令只会把密码用于验证，不会保存或输出密码；成功后该用户的 `role` 变为
`admin`。初始化操作会写入审计日志。管理员接口仍然要求 Flask Session 登录，
并在后端检查 `role` 字段。

管理员用户管理接口支持：

- `GET /api/admin/users?page=1&page_size=20&search=关键词`
- `GET /api/admin/users/<user_id>`
- `PATCH /api/admin/users/<user_id>/status`，请求体为
  `{"status": "active"}` 或 `{"status": "disabled"}`

状态接口只能操作普通用户，不能通过它修改管理员状态，因此不会误禁用最后
一个有效管理员。

用户名按不区分大小写的方式归一化保存和查询；时间字段统一使用带时区的
UTC ISO 8601 格式。登录失败在同一用户名和来源地址 15 分钟内达到 5 次后
暂时限流，返回 HTTP 429。
# TravelMate 成员 A 开发讲解

> 面向 Python 初学者的项目基础架构、用户认证和管理员功能说明。

## 1. 成员 A 完成了什么

成员 A 负责三类内容：

1. **项目基础架构**
   - Flask 应用创建
   - 配置管理
   - SQLite 数据库连接
   - 统一 JSON 返回格式
   - 错误处理
2. **用户认证**
   - 用户注册
   - 用户登录和退出
   - Flask Session 登录状态
   - 个人资料修改
   - 修改密码
   - CSRF 防护
3. **管理员基础管理**
   - 管理员权限判断
   - 用户列表和搜索
   - 用户详情
   - 启用或禁用普通用户
   - 审计日志
   - 首个管理员初始化脚本

成员 A 没有实现景点、行程规划、收藏和前端页面业务。

---

## 2. 项目目录总览

```text
TravelMate/
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── database/
│   ├── __init__.py
│   ├── connection.py
│   ├── schema.sql
│   └── users.py
├── routes/
│   ├── __init__.py
│   ├── base.py
│   ├── auth.py
│   └── admin.py
├── scripts/
│   ├── __init__.py
│   └── create_admin.py
├── utils/
│   ├── __init__.py
│   ├── decorators.py
│   ├── responses.py
│   └── validators.py
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_admin.py
    └── test_infrastructure.py
```

### Python 包是什么

包含 `__init__.py` 的目录可以作为 Python 包导入。例如：

```python
from database.connection import get_db
```

这里的 `database` 是包，`connection` 是模块，`get_db` 是函数。

---

## 3. 应用入口：`app.py`

文件：[app.py](../app.py)

### 3.1 `create_app()`：应用工厂

核心代码逻辑可以概括为：

```python
def create_app(config_name=None, overrides=None, init_database=True):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.update(overrides or {})
    app.register_blueprint(...)
    if init_database:
        init_db(app)
    return app
```

它做了几件事：

1. 创建 Flask 应用对象。
2. 读取开发、测试或生产配置。
3. 允许测试传入临时数据库路径。
4. 注册不同功能的 Blueprint。
5. 初始化数据库。
6. 注册错误处理和安全响应头。

### 3.2 什么是 Flask 应用工厂

Flask 应用工厂就是一个“创建应用的函数”。

好处是可以创建不同环境的应用：

```python
create_app("development")
create_app("testing")
create_app("production")
```

测试时可以使用临时数据库，而不是污染正式数据库。

### 3.3 Blueprint 是什么

Blueprint 可以理解为“路由模块”。

项目中按功能拆分：

- `base_bp`：基础首页
- `auth_bp`：注册、登录和个人资料
- `admin_bp`：管理员功能

如果把所有路由都写在 `app.py`，文件会越来越大，成员多人开发时也容易产生冲突。

### 3.4 应用启动方式

```python
app = create_app(init_database=False)

if __name__ == "__main__":
    init_db(app)
    app.run()
```

执行：

```powershell
.venv\Scripts\python.exe app.py
```

浏览器访问：

```text
http://127.0.0.1:5000/
```

### 3.5 为什么测试不直接使用全局 `app`

如果模块导入时立即初始化默认数据库，测试可能会创建：

```text
database/travelmate.db
```

现在测试使用：

```python
create_app(
    "testing",
    overrides={"DATABASE": str(tmp_path / "test.db")},
)
```

这样每个测试使用自己的临时数据库。

---

## 4. 配置文件：`config.py`

文件：[config.py](../config.py)

### 4.1 配置类

项目使用三个环境配置：

```python
DevelopmentConfig
TestingConfig
ProductionConfig
```

### 4.2 为什么要区分环境

开发环境、测试环境和生产环境的要求不同：

| 环境 | 主要特点 |
|---|---|
| development | 方便调试 |
| testing | 使用临时数据库 |
| production | 不允许使用默认密钥，Cookie 必须 Secure |

### 4.3 SECRET_KEY 的作用

Flask Session 默认使用签名 Cookie 保存数据。`SECRET_KEY` 用来防止用户伪造 Session。

正式环境通过环境变量设置：

```powershell
$env:TRAVELMATE_SECRET_KEY="正式环境密钥"
```

不能把正式密钥写入 Git。

### 4.4 Cookie 安全配置

```python
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = True
```

- `HttpOnly`：JavaScript 不能直接读取 Cookie，降低 XSS 窃取风险。
- `SameSite=Lax`：限制跨站请求携带 Cookie。
- `Secure=True`：只通过 HTTPS 发送 Cookie，生产环境应该开启。

---

## 5. 依赖文件：`requirements.txt`

文件：[requirements.txt](../requirements.txt)

```text
Flask>=3.0,<4.0
pytest>=8.0,<9.0
```

- Flask：Web 框架。
- pytest：测试框架。
- SQLite、Werkzeug、Jinja2 等由 Python 或 Flask 依赖提供。

安装：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 6. 数据库连接：`database/connection.py`

文件：[database/connection.py](../database/connection.py)

### 6.1 `get_db()`

```python
def get_db():
    if "db" not in g:
        connection = sqlite3.connect(...)
        g.db = connection
    return g.db
```

`g` 是 Flask 为当前请求提供的临时对象。

作用：

- 同一个请求内重复调用 `get_db()` 时复用同一个连接。
- 不需要每个函数都手动创建连接。

### 6.2 `close_db()`

请求结束时关闭连接，避免数据库连接长期占用资源。

### 6.3 `db_transaction()`

```python
with db_transaction():
    ...
```

正常执行完成时提交：

```python
database.commit()
```

发生异常时回滚：

```python
database.rollback()
```

这保证了一个业务操作要么全部成功，要么全部撤销。

例如，修改用户状态和写审计日志应该在同一个事务内完成。

### 6.4 SQLite 安全设置

项目启用了：

```sql
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA journal_mode = WAL;
```

- 外键约束：防止产生无效关联。
- busy timeout：数据库暂时被占用时等待。
- WAL：改善 SQLite 并发读写能力。

---

## 7. 数据表：`database/schema.sql`

文件：[database/schema.sql](../database/schema.sql)

### 7.1 `users` 表

主要字段：

| 字段 | 作用 |
|---|---|
| `id` | 用户唯一编号 |
| `username` | 展示用用户名 |
| `username_key` | 小写归一化用户名，用于唯一性查询 |
| `password_hash` | 密码哈希 |
| `email` | 邮箱 |
| `nickname` | 昵称 |
| `role` | `user` 或 `admin` |
| `status` | `active` 或 `disabled` |
| `created_at` | 创建时间 |
| `updated_at` | 修改时间 |
| `session_version` | 会话版本 |

### 7.2 为什么不能保存明文密码

如果数据库泄露，明文密码会直接暴露。

项目保存的是 Werkzeug 生成的哈希：

```python
generate_password_hash(password)
```

登录时使用：

```python
check_password_hash(password_hash, password)
```

系统不会尝试“解密”密码，而是重新计算并比较结果。

### 7.3 `session_version`

用户修改密码、状态被禁用等情况下，可以递增 `session_version`。

Session 中保存旧版本，后续请求查询数据库发现版本不一致，就会要求重新登录。

---

## 8. 用户数据操作：`database/users.py`

文件：[database/users.py](../database/users.py)

这个文件是数据访问层，主要负责：

- 查询用户
- 创建用户
- 修改资料
- 修改密码
- 分页查询
- 写审计日志

数据层只负责执行 SQL，不负责决定事务何时提交。

### 8.1 参数化 SQL

正确写法：

```python
database.execute(
    "SELECT * FROM users WHERE username_key = ?",
    (username_key,),
)
```

不能把用户输入直接拼接到 SQL 字符串中，否则可能产生 SQL 注入。

### 8.2 用户名归一化

注册和登录前都转换为小写：

```python
username_key = username.strip().lower()
```

所以 `ZhangSan` 和 `zhangsan` 被视为同一个账号。

### 8.3 公开用户信息

`public_user()` 和 `public_admin_user()` 使用字段白名单，只返回允许公开的信息。

这样即使数据库中存在 `password_hash`，也不会被接口返回。

---

## 9. 公共工具层：`utils/`

### 9.1 `utils/responses.py`

文件：[utils/responses.py](../utils/responses.py)

统一接口返回：

```json
{
  "success": true,
  "message": "操作成功",
  "data": {}
}
```

失败时：

```json
{
  "success": false,
  "message": "操作失败",
  "data": null
}
```

### 9.2 `utils/validators.py`

文件：[utils/validators.py](../utils/validators.py)

负责验证：

- 用户名
- 密码
- 邮箱
- 昵称

验证逻辑集中后，注册和修改资料可以复用同一套规则。

### 9.3 `utils/decorators.py`

文件：[utils/decorators.py](../utils/decorators.py)

包含三个重要装饰器：

#### `csrf_protected`

检查请求头中的：

```text
X-CSRF-Token
```

是否和 Session 中的 Token 一致。

#### `login_required`

检查：

1. 是否有用户 ID。
2. 是否有 Session 版本。
3. 用户是否存在。
4. 用户状态是否为 `active`。
5. Session 版本是否匹配。

#### `role_required("admin")`

先要求登录，再检查数据库中的角色。

```python
admin_required = role_required("admin")
```

普通用户不能通过修改前端请求获得管理员权限。

---

## 10. 用户认证路由：`routes/auth.py`

文件：[routes/auth.py](../routes/auth.py)

### 10.1 获取 CSRF Token

```http
GET /api/csrf-token
```

写操作前先获取 Token。

### 10.2 注册

```http
POST /api/register
```

流程：

1. 读取 JSON。
2. 校验用户名、密码、邮箱和昵称。
3. 将用户名归一化。
4. 查询是否重复。
5. 生成密码哈希。
6. 写入数据库。
7. 记录注册审计日志。
8. 返回公开用户信息。

注册时角色固定为 `user`，不会读取请求体中的 `role`。

### 10.3 登录

```http
POST /api/login
```

流程：

1. 查询登录失败次数。
2. 如果超过限制，返回 `429`。
3. 查询用户。
4. 使用 `check_password_hash()` 验证密码。
5. 检查用户状态。
6. 清理旧 Session。
7. 重新生成 CSRF Token。
8. 写入用户 ID 和 Session 版本。

### 10.4 修改密码

修改密码后递增 `session_version`，其他设备上的旧 Session 会在下一次请求时失效。

### 10.5 登录失败限流

同一用户名和 IP 在 15 分钟内失败 5 次后，第 6 次返回 `429`。

这是一个简单的 SQLite 限流方案，适合当前课程项目。

---

## 11. 管理员路由：`routes/admin.py`

文件：[routes/admin.py](../routes/admin.py)

### 11.1 用户列表

```http
GET /api/admin/users?page=1&page_size=20&search=zhang
```

支持：

- 分页
- 用户名搜索
- 结果不包含密码哈希

搜索中的 `%` 和 `_` 会被转义，避免被当作 LIKE 通配符。

### 11.2 用户详情

```http
GET /api/admin/users/<user_id>
```

管理员查看用户资料时会写审计日志。

### 11.3 修改用户状态

```http
PATCH /api/admin/users/<user_id>/status
```

请求体：

```json
{
  "status": "disabled"
}
```

只能修改普通用户，不能通过此接口修改管理员状态。

数据库更新条件中直接包含：

```sql
role = 'user'
```

这样可以缩小并发操作中的竞态窗口。

---

## 12. 管理员初始化脚本

文件：[scripts/create_admin.py](../scripts/create_admin.py)

运行：

```powershell
.venv\Scripts\python.exe -m scripts.create_admin
```

脚本要求输入已经注册的用户名和密码。

它不会：

- 自动创建固定管理员
- 在代码中保存密码
- 打印密码
- 打印密钥

验证成功后，只把已有用户的 `role` 修改为 `admin`。

---

## 13. 测试文件讲解

### `tests/conftest.py`

文件：[tests/conftest.py](../tests/conftest.py)

提供 pytest 公共夹具：

- 测试 Flask 应用
- 临时数据库
- 测试客户端
- CSRF 请求头

### `tests/test_auth.py`

文件：[tests/test_auth.py](../tests/test_auth.py)

测试：

- 注册
- 登录
- 退出
- 修改资料
- 修改密码
- 密码哈希
- CSRF
- 限流
- 用户名大小写
- 空白昵称

### `tests/test_admin.py`

文件：[tests/test_admin.py](../tests/test_admin.py)

测试：

- 未登录返回 `401`
- 普通用户返回 `403`
- 管理员查询用户
- 搜索用户
- 禁用普通用户
- 禁用用户无法登录
- 在线会话失效
- 不能禁用管理员
- 审计日志

### `tests/test_infrastructure.py`

文件：[tests/test_infrastructure.py](../tests/test_infrastructure.py)

测试：

- 导入应用不会污染默认数据库
- 数据库初始化幂等
- 时间格式统一

运行全部测试：

```powershell
.venv\Scripts\python.exe -m pytest -q
```

当前预期结果：

```text
31 passed
```

---

## 14. 一次完整请求的执行流程

以登录为例：

```text
浏览器
  ↓ POST /api/login
Flask 路由
  ↓ csrf_protected
读取 JSON
  ↓
检查登录失败次数
  ↓
查询 users 表
  ↓
check_password_hash()
  ↓
创建 Session
  ↓
返回统一 JSON
```

以管理员禁用用户为例：

```text
请求
  ↓
csrf_protected
  ↓
role_required("admin")
  ↓
验证目标用户 ID
  ↓
事务开始
  ↓
修改普通用户状态
  ↓
写审计日志
  ↓
事务提交
```

---

## 15. 老师答辩常见问题与参考回答

### 问题 1：为什么使用 Flask 应用工厂？

参考回答：

应用工厂把应用创建过程封装到 `create_app()` 中，可以根据不同环境加载不同配置。测试时可以传入临时数据库，生产环境可以使用正式配置，避免所有环境共用一个全局应用。

### 问题 2：为什么使用 Blueprint？

参考回答：

Blueprint 用来拆分路由模块。认证、管理员和基础路由分别放在不同文件中，降低文件复杂度和团队协作冲突。

### 问题 3：密码为什么不能直接保存？

参考回答：

明文密码一旦数据库泄露，用户密码会直接暴露。系统使用 `generate_password_hash()` 生成不可逆哈希，登录时使用 `check_password_hash()` 验证。

### 问题 4：Session 是什么？

参考回答：

Session 用来保存用户登录状态。项目在 Session 中保存用户 ID 和会话版本，后续请求根据这些信息确认用户是否仍然有效。

### 问题 5：为什么还要查询数据库，不能只相信 Session 吗？

参考回答：

因为用户可能被禁用，或者密码已经修改。如果只检查浏览器 Cookie，旧登录状态可能继续有效。每次访问受保护接口时查询数据库，可以立即发现状态或会话版本变化。

### 问题 6：普通用户如何不能变成管理员？

参考回答：

注册接口不读取客户端的 `role` 字段，服务端固定写入 `user`。个人资料接口也明确拒绝 `role` 和 `status` 字段。管理员接口则从数据库查询当前用户角色，不信任前端。

### 问题 7：CSRF 是什么？

参考回答：

CSRF 是跨站请求伪造。攻击者可能诱导用户浏览器带着登录 Cookie 发起写操作。项目要求请求携带 Session 中对应的 CSRF Token，Token 不匹配就返回 `403`。

### 问题 8：为什么 GET 接口不要求 CSRF？

参考回答：

GET 只读取数据，不应该改变服务器状态。CSRF 主要保护注册、登录、退出、修改资料和修改密码等写操作。

### 问题 9：为什么要使用参数化 SQL？

参考回答：

参数化 SQL 将 SQL 结构和用户输入分开，避免用户输入被当成 SQL 代码，从而降低 SQL 注入风险。

### 问题 10：为什么数据库操作要使用事务？

参考回答：

事务可以保证一组操作要么全部成功，要么全部回滚。例如禁用用户和写审计日志必须保持一致，不能只修改状态却没有审计记录。

### 问题 11：为什么测试不能使用正式数据库？

参考回答：

测试可能创建、修改或删除数据。使用临时 SQLite 数据库可以隔离测试数据，防止污染开发数据库和真实用户数据。

### 问题 12：如何让修改密码后其他设备退出？

参考回答：

数据库中保存 `session_version`。修改密码时递增版本，旧设备 Session 中仍是旧版本，下一次请求检查到版本不一致后就会被判定为登录失效。

### 问题 13：为什么管理员状态接口不能修改管理员？

参考回答：

这是为了防止误禁用最后一个管理员。SQL 更新条件明确要求目标用户的角色必须是 `user`，管理员不能通过这个接口被禁用。

### 问题 14：为什么需要审计日志？

参考回答：

审计日志可以记录谁在什么时间对哪个用户执行了什么操作，便于排查误操作、越权访问和安全事件。日志中不记录密码和密钥。

### 问题 15：登录失败为什么返回统一提示？

参考回答：

如果分别提示“用户不存在”和“密码错误”，攻击者可以用来枚举系统中的用户名。统一返回“用户名或密码错误”可以减少信息泄露。

### 问题 16：为什么用户名要转成小写？

参考回答：

如果不归一化，`Admin` 和 `admin` 可能被当成两个账号，容易造成混淆。项目使用 `username_key` 保存小写值，用于唯一性检查和登录查询。

### 问题 17：为什么要设置 `SESSION_COOKIE_HTTPONLY`？

参考回答：

开启后，客户端 JavaScript 不能直接读取 Session Cookie，可以降低部分跨站脚本攻击窃取 Cookie 的风险。

### 问题 18：为什么生产环境要设置 `SESSION_COOKIE_SECURE=True`？

参考回答：

这样浏览器只会通过 HTTPS 发送 Session Cookie，避免 Cookie 在普通 HTTP 连接中被窃听。

### 问题 19：项目当前有什么限制？

参考回答：

当前使用 SQLite，适合课程项目和小规模应用；高并发生产环境可以迁移到 PostgreSQL 或 MySQL。登录限流目前保存在 SQLite 中，多服务器部署时应改用 Redis 等共享存储。

### 问题 20：成员 A 和其他成员如何协作？

参考回答：

成员 A 提供公共数据库连接、统一响应格式、认证装饰器和用户身份字段。成员 B、C、D 应该复用这些公共模块，不要各自创建新的数据库连接、Session 字段或返回格式。

---

## 16. 答辩演示建议

建议按照以下顺序演示：

1. 启动 Flask。
2. 获取 CSRF Token。
3. 注册一个普通用户。
4. 登录普通用户。
5. 访问 `/api/user/info`。
6. 尝试访问管理员接口，展示 `403`。
7. 使用初始化脚本将已有用户提升为管理员。
8. 管理员登录。
9. 查询用户列表。
10. 搜索用户。
11. 禁用普通用户。
12. 展示该用户无法再次登录。
13. 展示测试结果：

```text
31 passed
```

演示时不要展示真实生产密钥、真实密码或真实用户信息。


# TravelMate 景点模块

本目录包含可合并到 TravelMate 项目的景点 API、数据访问、幂等初始化脚本和测试。代码不修改项目现有基础文件。

## 接入步骤

将 `routes/attractions.py`、`database/attractions.py` 和 `scripts/seed_attractions.py` 分别复制到项目同名目录；将测试复制到项目的 `tests/` 目录。

需要由成员 A 在基础架构中完成以下接入：

1. 在 `app.py` 注册 `attractions_bp`。
2. 在数据库初始化事务中调用 `migrate_attractions(database)`。
3. 确保迁移与 Blueprint 注册在应用启动/测试应用中均生效。

成员 C 未修改 `app.py`、`config.py`、`database/connection.py` 或 `database/schema.sql`。迁移函数可重复执行，不删除现有数据。景点数据操作复用项目的 `get_db()`、`db_transaction()` 和 `utc_now()`。

## 表结构

- `attraction_categories`：`id` 自增主键，`name` 和 `slug` 非空且唯一。
- `attractions`：`id` 自增主键；`category_id` 外键引用分类并限制删除；`slug` 唯一；包含城市、地址、描述、以分为单位的可空票价、开放时间、图片 URL、状态和 UTC 时间字段。
- 状态仅允许 `active` / `inactive`；票价为空或非负整数。
- 索引：景点状态、城市、分类和 ID 的复合索引。

## API

所有响应均包含 `success`、`message`、`data`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/attractions?page=1&page_size=20&category=natural&city=杭州市&q=西湖` | 分页查询，可按分类 slug、城市精确筛选，按关键词搜索名称和描述 |
| GET | `/api/attractions/categories` | 查询分类 |
| GET | `/api/attractions/<id>` | 查询景点详情；无效 ID 返回 400，不存在或非公开景点返回 404 |

列表只返回 `active` 景点，默认按名称和 ID 稳定排序。`page_size` 限制为 1–100。筛选值均使用 SQL 参数绑定；关键词中的 `%`、`_` 和反斜杠会按普通字符搜索。

## 初始化景点数据

在项目根目录执行：

```bash
python -m scripts.seed_attractions
```

此脚本会创建景点模块所需表（若尚未存在）并幂等写入少量演示分类和景点。已有同 slug 数据不会被覆盖。示例票价、营业时间和图片均留空；正式上线前应按数据来源补充并核验。

## 测试

将测试文件合并到项目后，在项目根目录运行：

```bash
python -m pytest -q tests/test_attractions.py
```

测试使用临时 SQLite 数据库，不会修改项目数据库。

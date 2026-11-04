# 景点数据导入与协作说明

面向全队：讲清楚数据存在哪、怎么导入、哪些操作会删数据、多人怎么共享。

## 1. 数据存在哪，为什么不跟着 Git 走

景点数据存在 `database/travelmate.db`（SQLite 文件），该文件已被 `.gitignore`
排除（`database/*.db`）。所以：

- **每个人本地数据库是独立的**，别人导入的数据不会自动出现在你电脑上；
- 表结构由 `migrate_attractions()` 在启动时自动创建/升级，这部分跟着代码走；
- 真正的"数据"要靠各自的导入脚本生成。

## 2. 可用脚本一览

| 脚本 | 作用 | 命令 | 联网 | 会删数据 |
| --- | --- | --- | --- | --- |
| `scripts.seed_attractions` | 写入 5 条基础景点 | `.venv/bin/python -m scripts.seed_attractions` | 否 | 否（幂等） |
| `scripts.seed_extra_attractions` | 基础 5 条 + 追加 12 条（非六城） | `.venv/bin/python -m scripts.seed_extra_attractions` | 否 | 否（幂等） |
| `scripts.rebuild_core_attractions` | 用 `data/core_attractions.json` 重建六城数据 | `.venv/bin/python -m scripts.rebuild_core_attractions` | 否 | **是（见第 4 节）** |
| `scripts.import_osm_attractions` | 导入本地 Overpass JSON | `.venv/bin/python -m scripts.import_osm_attractions data/beijing.json` | 否 | 否（按来源幂等） |
| `scripts.import_osm_pbf_attractions` | 导入本地 OSM PBF | `.venv/bin/python -m scripts.import_osm_pbf_attractions data/beijing.osm.pbf --city 北京市` | 否 | 否（按来源幂等） |
| `scripts.fetch_real_images` | 从 Wikimedia 抓真实图片 | `.venv/bin/python -m scripts.fetch_real_images` | **是** | 否（只更新 image_url） |

首次拉代码后，最少跑这一条就能有可演示的数据：

```bash
.venv/bin/python -m scripts.seed_extra_attractions
```

想要 120 条六城精选数据：

```bash
.venv/bin/python -m scripts.rebuild_core_attractions
```

## 3. `data/` 目录的提交规则

`.gitignore` 里的规则：

```gitignore
!data/
data/*
!data/core_attractions.py
!data/core_attractions.json
```

结论：

| 文件 | 能否提交 | 说明 |
| --- | --- | --- |
| `data/core_attractions.json` | 能 | 团队共享的数据集 |
| `data/core_attractions.py` | 能 | 数据校验/解析代码 |
| `data/beijing.json` 等 | 不能 | 原始数据大、涉及 ODbL 许可 |
| `data/*.pbf` | 不能 | 动辄上百 MB |

## 4. 会删数据的操作

`scripts.rebuild_core_attractions` 的执行逻辑是：

```sql
DELETE FROM attractions WHERE city IN ('北京市','上海市','广州市','深圳市','成都市','西安市');
```

然后再写入 JSON 里的 120 条。也就是说：

- 如果你手动往这六个城市导过数据，**跑一次 rebuild 就全没了**；
- 其他城市（杭州、南京、张家界等）**不受影响**。

**协作要求**：谁要跑 rebuild，先在群里说一声，避免覆盖别人刚导入的数据。

## 5. 多人共享数据的正确流程

原始 JSON/PBF 不能提交，所以只能共享"加工后的数据集"：

1. 本地导入并验证效果（`import_osm_attractions`）；
2. 把确认要保留的记录整理进 `data/core_attractions.json`（保持原有字段结构）；
3. 提交这个文件并推送：

```bash
git add data/core_attractions.json
git commit -m "补充 XX 城市景点数据"
git push
```

4. 其他人拉取后执行：

```bash
.venv/bin/python -m scripts.rebuild_core_attractions
```

这样大家得到的是同一份数据。

## 6. 字段与约束

`attractions` 表关键字段：

| 字段 | 说明 |
| --- | --- |
| `name` / `slug` | 名称与唯一标识，`slug` 唯一 |
| `city` | 城市名，当前数据统一带"市"（如 `杭州市`） |
| `category_id` | 关联 `attraction_categories` |
| `ticket_price_cents` | 门票，单位是**分**，0 表示免费，`NULL` 表示未知 |
| `image_url` | 图片直链，可为空 |
| `latitude` / `longitude` | 经纬度，导入 OSM 数据后才有 |
| `source` / `source_id` | 来源标记，OSM 导入用于幂等 |

注意：

- 不要提交真实用户数据或个人数据库文件；
- 使用 OSM 数据必须遵守 ODbL，公开页面要保留
  "© OpenStreetMap contributors" 及来源链接；
- 图片必须是有授权的链接，不要塞本地未授权图片。

## 7. 数据与 AI 助手的关系

AI 助手（`/agent`）生成行程和回答问题时，是从数据库**实时查询**景点作为上下文的：

- 景点越多，可安排的城市和路线越丰富；
- 数据库为空时，`/api/agent/plan` 会返回 404 并提示先导入景点；
- 模型返回的 `attraction_id` 会做二次校验，数据里没有的会被剔除。

所以导入数据之后，AI 助手的效果会同步变好，不需要改代码。

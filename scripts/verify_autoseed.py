"""校验启动自愈后核心景点数据是否完整（本地自检脚本）。"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module  # noqa: E402
from database.attractions import sync_core_attractions  # noqa: E402
from database.connection import init_db  # noqa: E402

init_db(app_module.app)

connection = sqlite3.connect(app_module.app.config["DATABASE"])
connection.row_factory = sqlite3.Row

print("database:", app_module.app.config["DATABASE"])
print("total:", connection.execute("SELECT COUNT(*) FROM attractions").fetchone()[0])
print(
    "core:",
    connection.execute(
        "SELECT COUNT(*) FROM attractions WHERE source = 'core'"
    ).fetchone()[0],
)
print(
    "cities:",
    connection.execute(
        "SELECT COUNT(DISTINCT city) FROM attractions WHERE source = 'core'"
    ).fetchone()[0],
)
rows = connection.execute(
    "SELECT c.slug AS slug, COUNT(*) AS cnt FROM attractions a "
    "JOIN attraction_categories c ON c.id = a.category_id "
    "GROUP BY c.slug ORDER BY c.slug"
).fetchall()
print("by_category:", [(row["slug"], row["cnt"]) for row in rows])
state_row = connection.execute(
    "SELECT value FROM app_state WHERE key = 'core_attractions_sha256'"
).fetchone()
print("state:", state_row["value"][:16] if state_row else None)
print("second_sync (应为 0):", sync_core_attractions(connection))

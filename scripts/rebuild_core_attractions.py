"""用核心城市景点数据重建本地演示数据库。

数据来源固定为仓库内 ``data/core_attractions.json``，实际写入逻辑与
``init_db`` 中的启动自愈共用 ``database.attractions.rebuild_core_attractions``，
避免脚本与线上运行时出现两套导入代码。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from database.attractions import (  # noqa: E402
    migrate_attractions,
    rebuild_core_attractions,
    seed_initial_attractions,
)
from database.connection import db_transaction  # noqa: E402


def main() -> None:
    app = create_app(init_database=False)
    with app.app_context():
        with db_transaction() as database:
            migrate_attractions(database)
            seed_initial_attractions(database)
            deleted, inserted = rebuild_core_attractions(database)
        print(f"数据库: {app.config['DATABASE']}")
        print(f"已删除旧核心景点 {deleted} 条，写入核心景点 {inserted} 条")


if __name__ == "__main__":
    main()

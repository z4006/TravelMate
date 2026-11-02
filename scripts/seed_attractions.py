"""初始化景点演示数据。"""

from app import create_app
from database.attractions import migrate_attractions, seed_initial_attractions
from database.connection import db_transaction


def main() -> None:
    app = create_app(init_database=False)
    with app.app_context():
        with db_transaction() as database:
            migrate_attractions(database)
            seed_initial_attractions(database)


if __name__ == "__main__":
    main()

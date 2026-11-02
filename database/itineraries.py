"""收藏和行程的数据访问及业务表初始化。"""

import sqlite3
from typing import Any

from database.connection import db_transaction, get_db, utc_now


def ensure_itinerary_tables(database: sqlite3.Connection | None = None) -> None:
    """创建 D 模块业务表；重复执行不会破坏已有数据。"""

    connection = database or get_db()
    with db_transaction() if database is None else _existing_transaction(connection):
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                attraction_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (user_id, attraction_id),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (attraction_id) REFERENCES attractions (id)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_favorites_user
                ON favorites (user_id);
            CREATE INDEX IF NOT EXISTS ix_favorites_attraction
                ON favorites (attraction_id);

            CREATE TABLE IF NOT EXISTS itineraries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_itineraries_user
                ON itineraries (user_id);

            CREATE TABLE IF NOT EXISTS itinerary_attractions (
                itinerary_id INTEGER NOT NULL,
                attraction_id INTEGER NOT NULL,
                visit_date TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                PRIMARY KEY (itinerary_id, attraction_id),
                FOREIGN KEY (itinerary_id) REFERENCES itineraries (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (attraction_id) REFERENCES attractions (id)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_itinerary_attractions_itinerary
                ON itinerary_attractions (itinerary_id, sort_order);
            """
        )


class _existing_transaction:
    def __init__(self, database: sqlite3.Connection):
        self.database = database

    def __enter__(self) -> sqlite3.Connection:
        return self.database

    def __exit__(self, exception_type, exception, traceback) -> bool:
        return False


def attraction_exists(database: sqlite3.Connection, attraction_id: int) -> bool:
    try:
        return database.execute(
            "SELECT 1 FROM attractions WHERE id = ?", (attraction_id,)
        ).fetchone() is not None
    except sqlite3.OperationalError as error:
        if "no such table" in str(error).lower():
            return False
        raise


def _attraction_columns(database: sqlite3.Connection) -> set[str]:
    return {
        row["name"]
        for row in database.execute("PRAGMA table_info(attractions)").fetchall()
    }


def _attraction_select(database: sqlite3.Connection, alias: str = "a") -> str:
    columns = _attraction_columns(database)
    selected = []
    for column in (
        "name",
        "city",
        "cover_image",
        "image_url",
        "address",
        "opening_hours",
        "ticket_price_cents",
    ):
        if column in columns:
            selected.append(f"{alias}.{column}")
    return ", ".join(selected) or "NULL AS attraction_name"


def create_favorite(database: sqlite3.Connection, user_id: int, attraction_id: int):
    cursor = database.execute(
        "INSERT INTO favorites (user_id, attraction_id, created_at) "
        "VALUES (?, ?, ?)",
        (user_id, attraction_id, utc_now()),
    )
    row = database.execute(
        "SELECT id, user_id, attraction_id, created_at FROM favorites WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return dict(row)


def list_favorites(database: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    columns = _attraction_columns(database)
    if "id" in columns:
        rows = database.execute(
            "SELECT f.id, f.attraction_id, f.created_at, "
            f"{_attraction_select(database)} FROM favorites f "
            "JOIN attractions a ON a.id = f.attraction_id "
            "WHERE f.user_id = ? ORDER BY f.created_at DESC, f.id DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = database.execute(
            "SELECT id, attraction_id, created_at FROM favorites "
            "WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_favorite(
    database: sqlite3.Connection, user_id: int, attraction_id: int
) -> bool:
    cursor = database.execute(
        "DELETE FROM favorites WHERE user_id = ? AND attraction_id = ?",
        (user_id, attraction_id),
    )
    return cursor.rowcount == 1


def create_itinerary(
    database: sqlite3.Connection,
    user_id: int,
    title: str,
    start_date: str | None,
    end_date: str | None,
    notes: str | None,
    attractions: list[dict[str, Any]],
) -> dict[str, Any]:
    now = utc_now()
    cursor = database.execute(
        "INSERT INTO itineraries "
        "(user_id, title, start_date, end_date, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, title, start_date, end_date, notes, now, now),
    )
    itinerary_id = cursor.lastrowid
    database.executemany(
        "INSERT INTO itinerary_attractions "
        "(itinerary_id, attraction_id, visit_date, sort_order, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (
                itinerary_id,
                item["attraction_id"],
                item.get("visit_date"),
                item.get("sort_order", index),
                item.get("notes"),
            )
            for index, item in enumerate(attractions)
        ],
    )
    return get_itinerary(database, user_id, itinerary_id)


def list_itineraries(database: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = database.execute(
        "SELECT id, title, start_date, end_date, notes, created_at, updated_at "
        "FROM itineraries WHERE user_id = ? ORDER BY start_date, id",
        (user_id,),
    ).fetchall()
    return [_with_attractions(database, dict(row)) for row in rows]


def get_itinerary(
    database: sqlite3.Connection, user_id: int, itinerary_id: int
) -> dict[str, Any] | None:
    row = database.execute(
        "SELECT id, title, start_date, end_date, notes, created_at, updated_at "
        "FROM itineraries WHERE id = ? AND user_id = ?",
        (itinerary_id, user_id),
    ).fetchone()
    return _with_attractions(database, dict(row)) if row else None


def update_itinerary(
    database: sqlite3.Connection,
    user_id: int,
    itinerary_id: int,
    title: str,
    start_date: str | None,
    end_date: str | None,
    notes: str | None,
    attractions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    cursor = database.execute(
        "UPDATE itineraries SET title = ?, start_date = ?, end_date = ?, "
        "notes = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (title, start_date, end_date, notes, utc_now(), itinerary_id, user_id),
    )
    if cursor.rowcount != 1:
        return None
    database.execute(
        "DELETE FROM itinerary_attractions WHERE itinerary_id = ?", (itinerary_id,)
    )
    database.executemany(
        "INSERT INTO itinerary_attractions "
        "(itinerary_id, attraction_id, visit_date, sort_order, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (
                itinerary_id,
                item["attraction_id"],
                item.get("visit_date"),
                item.get("sort_order", index),
                item.get("notes"),
            )
            for index, item in enumerate(attractions)
        ],
    )
    return get_itinerary(database, user_id, itinerary_id)


def delete_itinerary(
    database: sqlite3.Connection, user_id: int, itinerary_id: int
) -> bool:
    cursor = database.execute(
        "DELETE FROM itineraries WHERE id = ? AND user_id = ?",
        (itinerary_id, user_id),
    )
    return cursor.rowcount == 1


def _with_attractions(database: sqlite3.Connection, itinerary: dict[str, Any]):
    columns = _attraction_columns(database)
    if "id" in columns:
        rows = database.execute(
            "SELECT ia.attraction_id, ia.visit_date, ia.sort_order, ia.notes, "
            f"{_attraction_select(database)} FROM itinerary_attractions ia "
            "JOIN attractions a ON a.id = ia.attraction_id "
            "WHERE ia.itinerary_id = ? ORDER BY ia.sort_order",
            (itinerary["id"],),
        ).fetchall()
    else:
        rows = database.execute(
            "SELECT attraction_id, visit_date, sort_order, notes "
            "FROM itinerary_attractions WHERE itinerary_id = ? ORDER BY sort_order",
            (itinerary["id"],),
        ).fetchall()
    itinerary["attractions"] = [dict(row) for row in rows]
    return itinerary

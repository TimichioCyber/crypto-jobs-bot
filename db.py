from __future__ import annotations

import aiosqlite

DB_PATH = "bot.db"

CREATE_USERS_SQL = """
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    date_range TEXT NOT NULL
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_USERS_SQL)
        await db.commit()


async def ensure_user(user_id: int, default_role: str, default_date_range: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO user_preferences (user_id, role, date_range)
            VALUES (?, ?, ?)
            """,
            (user_id, default_role, default_date_range),
        )
        await db.commit()


async def get_user_preferences(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT role, date_range FROM user_preferences WHERE user_id = ?",
            (user_id,),
        )
        prefs_row = await cursor.fetchone()

    role = prefs_row["role"] if prefs_row else None
    date_range = prefs_row["date_range"] if prefs_row else None

    return {
        "role": role,
        "date_range": date_range,
    }


async def set_role(user_id: int, role: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_preferences (user_id, role, date_range)
            VALUES (?, ?, '7')
            ON CONFLICT(user_id) DO UPDATE SET role = excluded.role
            """,
            (user_id, role),
        )
        await db.commit()


async def set_date_range(user_id: int, date_range: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_preferences (user_id, role, date_range)
            VALUES (?, 'developer', ?)
            ON CONFLICT(user_id) DO UPDATE SET date_range = excluded.date_range
            """,
            (user_id, date_range),
        )
        await db.commit()

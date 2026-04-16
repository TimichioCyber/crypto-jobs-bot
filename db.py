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

CREATE_COMPANIES_SQL = """
CREATE TABLE IF NOT EXISTS user_companies (
    user_id INTEGER NOT NULL,
    board_token TEXT NOT NULL,
    PRIMARY KEY (user_id, board_token)
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_USERS_SQL)
        await db.execute(CREATE_COMPANIES_SQL)
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

        cursor = await db.execute(
            "SELECT board_token FROM user_companies WHERE user_id = ? ORDER BY board_token",
            (user_id,),
        )
        company_rows = await cursor.fetchall()

    role = prefs_row["role"] if prefs_row else None
    date_range = prefs_row["date_range"] if prefs_row else None
    companies = {row["board_token"] for row in company_rows}

    return {
        "role": role,
        "date_range": date_range,
        "companies": companies,
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


async def toggle_company(user_id: int, board_token: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT 1 FROM user_companies
            WHERE user_id = ? AND board_token = ?
            """,
            (user_id, board_token),
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute(
                """
                DELETE FROM user_companies
                WHERE user_id = ? AND board_token = ?
                """,
                (user_id, board_token),
            )
        else:
            await db.execute(
                """
                INSERT INTO user_companies (user_id, board_token)
                VALUES (?, ?)
                """,
                (user_id, board_token),
            )

        await db.commit()


async def set_default_companies_if_empty(user_id: int, board_tokens: list[str]) -> None:
    prefs = await get_user_preferences(user_id)
    if prefs["companies"]:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        for token in board_tokens:
            await db.execute(
                """
                INSERT OR IGNORE INTO user_companies (user_id, board_token)
                VALUES (?, ?)
                """,
                (user_id, token),
            )
        await db.commit()

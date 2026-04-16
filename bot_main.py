"""
Crypto Jobs Telegram Bot — FINAL
Парсит крипто-вакансии с ATS (Greenhouse/Lever/Ashby/SmartRecruiters) + CryptoJobs + AngelList.
SQLite для хранения фильтров и отправленных вакансий (дедуп).
Фоновый цикл через asyncio (без job_queue extra).
"""

import asyncio
import logging
import os
import sqlite3
import json
import html
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# --- Parsers ---
from parsers_cryptojobs import parse_cryptojobs
from parsers_angellist import parse_angellist
from parsers_greenhouse import parse_greenhouse
from parsers_lever import parse_lever
from parsers_ashby import parse_ashby
from parsers_smartrecruiters import parse_smartrecruiters

from filters import apply_filters

load_dotenv()

# --- Логирование ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- Константы ---
DB_PATH = os.getenv("DB_PATH", "bot.db")
SEARCH_INTERVAL = int(os.getenv("SEARCH_INTERVAL", "3600"))  # сек
MAX_PER_BATCH = int(os.getenv("MAX_PER_BATCH", "10"))

POSITIONS = {
    "developer": "Разработчик 👨‍💻",
    "designer": "Дизайнер 🎨",
    "content": "Контент-мейкер ✍️",
    "marketing": "Маркетолог 📢",
    "product": "Product Manager 📊",
    "hr": "HR 👥",
    "community": "Community Manager 💬",
    "trader": "Трейдер 📈",
    "analyst": "Аналитик 🔬",
    "bizdev": "BD / Sales 💼",
}

FORMATS = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "freelance": "Фриланс",
    "internship": "Стажировка",
    "remote": "Remote",
}

DATE_RANGES = {
    "1d": "За сутки",
    "3d": "За 3 дня",
    "7d": "За неделю",
    "30d": "За месяц",
    "all": "За всё время",
}

# --- БД ---
def db_init():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            prefs TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sent_jobs (
            user_id INTEGER NOT NULL,
            job_url TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            PRIMARY KEY (user_id, job_url)
        )
    """)
    conn.commit()
    conn.close()


def db_get_prefs(user_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT prefs FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return _default_prefs()
    try:
        prefs = json.loads(row[0])
        prefs["positions"] = set(prefs.get("positions", []))
        prefs["formats"] = set(prefs.get("formats", []))
        return prefs
    except Exception:
        return _default_prefs()


def db_save_prefs(user_id: int, prefs: dict):
    payload = {
        "positions": list(prefs.get("positions", [])),
        "formats": list(prefs.get("formats", [])),
        "date_range": prefs.get("date_range", "7d"),
    }
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (user_id, prefs, active, created_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(user_id) DO UPDATE SET prefs = excluded.prefs
    """, (user_id, json.dumps(payload), datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def db_set_active(user_id: int, active: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET active = ? WHERE user_id = ?", (1 if active else 0, user_id))
    conn.commit()
    conn.close()


def db_all_active_users() -> list[int]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE active = 1")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def db_is_sent(user_id: int, url: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM sent_jobs WHERE user_id = ? AND job_url = ?", (user_id, url))
    row = c.fetchone()
    conn.close()
    return row is not None


def db_mark_sent(user_id: int, url: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO sent_jobs (user_id, job_url, sent_at) VALUES (?, ?, ?)",
        (user_id, url, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def _default_prefs() -> dict:
    return {"positions": set(), "formats": set(), "date_range": "7d"}


# --- Клавиатуры ---
def kb_positions(prefs: dict) -> InlineKeyboardMarkup:
    rows = []
    items = list(POSITIONS.items())
    for i in range(0, len(items), 2):
        row = []
        for k, name in items[i:i+2]:
            prefix = "✅ " if k in prefs["positions"] else "☐ "
            row.append(InlineKeyboardButton(f"{prefix}{name}", callback_data=f"pos_{k}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("➡️ Формат", callback_data="go_format")])
    return InlineKeyboardMarkup(rows)


def kb_formats(prefs: dict) -> InlineKeyboardMarkup:
    rows = []
    for k, name in FORMATS.items():
        prefix = "✅ " if k in prefs["formats"] else "☐ "
        rows.append([InlineKeyboardButton(f"{prefix}{name}", callback_data=f"fmt_{k}")])
    rows.append([InlineKeyboardButton("➡️ Период", callback_data="go_dates")])
    return InlineKeyboardMarkup(rows)


def kb_dates(prefs: dict) -> InlineKeyboardMarkup:
    rows = []
    for k, name in DATE_RANGES.items():
        prefix = "✅ " if prefs.get("date_range") == k else "☐ "
        rows.append([InlineKeyboardButton(f"{prefix}{name}", callback_data=f"date_{k}")])
    rows.append([InlineKeyboardButton("🔍 Начать поиск", callback_data="go_search")])
    return InlineKeyboardMarkup(rows)


# --- Хендлеры ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prefs = db_get_prefs(user_id)
    db_save_prefs(user_id, prefs)
    # НЕ активируем здесь! Активация только при "Начать поиск"
    logger.info(f"User {user_id} /start")

    await update.message.reply_text(
        "👋 Привет! Я ищу крипто-вакансии.\n\n"
        "Шаг 1/3 — выбери должности:",
        reply_markup=kb_positions(prefs),
    )


async def cb_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    pos = q.data.split("_", 1)[1]

    prefs = db_get_prefs(user_id)
    if pos in prefs["positions"]:
        prefs["positions"].discard(pos)
    else:
        prefs["positions"].add(pos)
    db_save_prefs(user_id, prefs)

    selected = ", ".join(POSITIONS[p] for p in prefs["positions"]) or "ничего"
    await q.edit_message_text(
        f"Шаг 1/3 — должности\n\n📍 Выбрано: {selected}",
        reply_markup=kb_positions(prefs),
    )


async def cb_go_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    prefs = db_get_prefs(q.from_user.id)
    await q.edit_message_text(
        "Шаг 2/3 — формат работы (можешь не выбирать, тогда любой):",
        reply_markup=kb_formats(prefs),
    )


async def cb_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    fmt = q.data.split("_", 1)[1]

    prefs = db_get_prefs(user_id)
    if fmt in prefs["formats"]:
        prefs["formats"].discard(fmt)
    else:
        prefs["formats"].add(fmt)
    db_save_prefs(user_id, prefs)

    selected = ", ".join(FORMATS[f] for f in prefs["formats"]) or "любой"
    await q.edit_message_text(
        f"Шаг 2/3 — формат\n\n📋 Выбрано: {selected}",
        reply_markup=kb_formats(prefs),
    )


async def cb_go_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    prefs = db_get_prefs(q.from_user.id)
    await q.edit_message_text(
        "Шаг 3/3 — за какой период показывать вакансии:",
        reply_markup=kb_dates(prefs),
    )


async def cb_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    dr = q.data.split("_", 1)[1]

    prefs = db_get_prefs(user_id)
    prefs["date_range"] = dr
    db_save_prefs(user_id, prefs)

    await q.edit_message_text(
        f"Шаг 3/3 — период\n\n🗓 Выбрано: {DATE_RANGES[dr]}",
        reply_markup=kb_dates(prefs),
    )


async def cb_go_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    prefs = db_get_prefs(user_id)

    if not prefs["positions"]:
        await q.edit_message_text("⚠️ Выбери хотя бы одну должность! /start")
        return

    db_set_active(user_id, True)
    logger.info(f"User {user_id} search start: {prefs}")

    await q.edit_message_text(
        "🔍 Поиск запущен!\n\n"
        f"Интервал: каждые {SEARCH_INTERVAL // 60} мин\n"
        f"Период вакансий: {DATE_RANGES[prefs['date_range']]}\n\n"
        "Команды:\n"
        "/status — текущие фильтры\n"
        "/pause — пауза\n"
        "/resume — возобновить\n"
        "/stop — остановить\n"
        "/help — справка"
    )

    # Первый прогон — сразу
    asyncio.create_task(search_for_user(context.application, user_id))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prefs = db_get_prefs(user_id)
    positions = ", ".join(POSITIONS[p] for p in prefs["positions"]) or "—"
    formats = ", ".join(FORMATS[f] for f in prefs["formats"]) or "любой"
    dr = DATE_RANGES.get(prefs.get("date_range", "7d"), "—")

    await update.message.reply_text(
        f"📊 <b>Твои фильтры</b>\n\n"
        f"💼 Должности: {positions}\n"
        f"📋 Формат: {formats}\n"
        f"🗓 Период: {dr}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_set_active(update.effective_user.id, False)
    await update.message.reply_text("⏸ Поиск на паузе. /resume — возобновить.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_set_active(update.effective_user.id, True)
    await update.message.reply_text("▶️ Поиск возобновлён.")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_set_active(update.effective_user.id, False)
    await update.message.reply_text("🛑 Остановлено. /start — начать заново.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Crypto Jobs Bot</b>\n\n"
        "Ищу крипто-вакансии и шлю тебе каждый час.\n\n"
        "<b>Команды:</b>\n"
        "/start — настроить фильтры\n"
        "/status — текущие фильтры\n"
        "/pause — пауза\n"
        "/resume — возобновить\n"
        "/stop — остановить\n"
        "/help — эта справка\n\n"
        "<b>Источники:</b>\n"
        "• CryptoJobs.com\n"
        "• AngelList (Wellfound)\n"
        "• Greenhouse (Coinbase, Kraken, OpenSea…)\n"
        "• Lever (Chainlink, Solana, DFINITY…)\n"
        "• Ashby (различные крипто-компании)\n"
        "• SmartRecruiters",
        parse_mode=ParseMode.HTML,
    )


# --- Поиск ---
async def fetch_all_jobs() -> list[dict]:
    """Гоним все парсеры параллельно, собираем в одну кучу."""
    parsers = [
        ("CryptoJobs", parse_cryptojobs),
        ("AngelList", parse_angellist),
        ("Greenhouse", parse_greenhouse),
        ("Lever", parse_lever),
        ("Ashby", parse_ashby),
        ("SmartRecruiters", parse_smartrecruiters),
    ]
    tasks = [asyncio.create_task(p()) for _, p in parsers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    jobs: list[dict] = []
    for (name, _), res in zip(parsers, results):
        if isinstance(res, Exception):
            logger.error(f"Parser {name} failed: {res}")
            continue
        if not res:
            continue
        logger.info(f"Parser {name}: {len(res)} jobs")
        jobs.extend(res)

    # Дедуп по URL
    seen = set()
    unique = []
    for j in jobs:
        url = j.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(j)
    return unique


def format_job(job: dict) -> str:
    def esc(s):
        return html.escape(str(s or "N/A"))

    title = esc(job.get("title"))
    company = esc(job.get("company"))
    salary = esc(job.get("salary", "Не указана"))
    location = esc(job.get("location"))
    fmt = esc(job.get("format"))
    source = esc(job.get("source", ""))
    url = job.get("url", "#")
    desc = html.escape(str(job.get("description", ""))[:240]).rstrip()

    return (
        f"<b>{title}</b>\n"
        f"🏢 {company}\n\n"
        f"💰 {salary}\n"
        f"📍 {location}\n"
        f"💼 {fmt}\n"
        f"🌐 {source}\n\n"
        f"<i>{desc}…</i>\n\n"
        f'<a href="{url}">Подробнее →</a>'
    )


async def search_for_user(app: Application, user_id: int):
    """Один прогон поиска для одного юзера."""
    try:
        prefs = db_get_prefs(user_id)
        if not prefs["positions"]:
            logger.debug(f"search_for_user u{user_id}: skip (no positions)")
            return

        jobs = await fetch_all_jobs()
        filtered = apply_filters(jobs, prefs)
        logger.info(f"search_for_user u{user_id}: {len(jobs)} total → {len(filtered)} filtered | positions={list(prefs['positions'])}")

        # Убираем уже отправленные
        new_jobs = [j for j in filtered if not db_is_sent(user_id, j.get("url", ""))]

        if not new_jobs:
            await app.bot.send_message(user_id, "😴 Новых вакансий нет.")
            return

        sent = 0
        for job in new_jobs[:MAX_PER_BATCH]:
            try:
                await app.bot.send_message(
                    user_id,
                    format_job(job),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False,
                )
                db_mark_sent(user_id, job.get("url", ""))
                sent += 1
                await asyncio.sleep(0.5)  # антифлуд
            except Exception as e:
                logger.error(f"Send fail u{user_id}: {e}")

        logger.info(f"Sent {sent} jobs to u{user_id}")
    except Exception as e:
        logger.exception(f"search_for_user u{user_id} fail: {e}")


async def search_loop(app: Application):
    """Фоновый цикл — обходит всех активных юзеров каждые SEARCH_INTERVAL сек."""
    # Первый запуск через 30 сек (дать боту проснуться)
    await asyncio.sleep(30)
    while True:
        try:
            users = db_all_active_users()
            logger.info(f"Loop tick: {len(users)} active users")
            for user_id in users:
                await search_for_user(app, user_id)
                await asyncio.sleep(2)
        except Exception as e:
            logger.exception(f"search_loop error: {e}")
        await asyncio.sleep(SEARCH_INTERVAL)


async def on_startup(app: Application):
    logger.info("Bot startup — launching search loop")
    asyncio.create_task(search_loop(app))


# --- main ---
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан!")

    db_init()

    app = (
        Application.builder()
        .token(token)
        .post_init(on_startup)
        .build()
    )

    # Команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("help", cmd_help))

    # Коллбэки
    app.add_handler(CallbackQueryHandler(cb_position, pattern=r"^pos_"))
    app.add_handler(CallbackQueryHandler(cb_go_format, pattern=r"^go_format$"))
    app.add_handler(CallbackQueryHandler(cb_format, pattern=r"^fmt_"))
    app.add_handler(CallbackQueryHandler(cb_go_dates, pattern=r"^go_dates$"))
    app.add_handler(CallbackQueryHandler(cb_date, pattern=r"^date_"))
    app.add_handler(CallbackQueryHandler(cb_go_search, pattern=r"^go_search$"))

    logger.info("Bot started — polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

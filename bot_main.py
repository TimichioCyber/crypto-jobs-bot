from __future__ import annotations

import logging
import os
from html import escape

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import (
    DATE_LABELS,
    DEFAULT_DATE_RANGE,
    DEFAULT_ROLE,
    GREENHOUSE_BOARDS,
    MAX_RESULTS_PER_SEARCH,
    ROLE_LABELS,
)
from db import (
    ensure_user,
    get_user_preferences,
    init_db,
    set_date_range,
    set_default_companies_if_empty,
    set_role,
    toggle_company,
)
from filters import filter_jobs
from greenhouse_client import fetch_jobs_for_boards

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def role_keyboard(current_role: str) -> InlineKeyboardMarkup:
    rows = []
    for role_key, role_label in ROLE_LABELS.items():
        marker = "✅ " if role_key == current_role else "☐ "
        rows.append([InlineKeyboardButton(f"{marker}{role_label}", callback_data=f"role:{role_key}")])

    rows.append([InlineKeyboardButton("➡️ Next: Date range", callback_data="go:date")])
    return InlineKeyboardMarkup(rows)


def date_keyboard(current_range: str) -> InlineKeyboardMarkup:
    rows = []
    for days, label in DATE_LABELS.items():
        marker = "✅ " if days == current_range else "☐ "
        rows.append([InlineKeyboardButton(f"{marker}{label}", callback_data=f"date:{days}")])

    rows.append([InlineKeyboardButton("➡️ Next: Companies", callback_data="go:companies")])
    return InlineKeyboardMarkup(rows)


def companies_keyboard(selected_companies: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for token, label in GREENHOUSE_BOARDS.items():
        marker = "✅ " if token in selected_companies else "☐ "
        rows.append([InlineKeyboardButton(f"{marker}{label}", callback_data=f"company:{token}")])

    rows.append([InlineKeyboardButton("🚀 Search jobs", callback_data="run:search")])
    return InlineKeyboardMarkup(rows)


async def prefs_text(user_id: int) -> str:
    prefs = await get_user_preferences(user_id)

    role = ROLE_LABELS.get(prefs["role"] or DEFAULT_ROLE, DEFAULT_ROLE)
    date_label = DATE_LABELS.get(prefs["date_range"] or DEFAULT_DATE_RANGE, DEFAULT_DATE_RANGE)

    companies = prefs["companies"] or set(GREENHOUSE_BOARDS.keys())
    companies_text = ", ".join(GREENHOUSE_BOARDS[c] for c in sorted(companies) if c in GREENHOUSE_BOARDS)

    return (
        "Your filters:\n"
        f"• Role: {role}\n"
        f"• Date range: {date_label}\n"
        f"• Companies: {companies_text}"
    )


def format_job(index: int, job: dict) -> str:
    title = escape(job["title"])
    company = escape(job["company"])
    location = escape(job["location"])
    employment_type = escape(job["employment_type"])
    salary = escape(job["salary"])
    posted_at = escape(job["posted_at_human"])
    source = escape(job["source"])
    role = escape(job["detected_role"])
    url = escape(job["url"])

    lines = [
        f"<b>{index}. {title}</b>",
        f"🏢 {company}",
        f"📍 {location}",
        f"💼 {employment_type}",
        f"💰 {salary}",
        f"🕒 {posted_at}",
        f"🏷 Role: {role}",
        f"🔎 Source: {source}",
    ]

    if url:
        lines.append(f'🔗 <a href="{url}">Open job</a>')

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        return

    await ensure_user(user.id, DEFAULT_ROLE, DEFAULT_DATE_RANGE)
    await set_default_companies_if_empty(user.id, list(GREENHOUSE_BOARDS.keys()))

    prefs = await get_user_preferences(user.id)

    await update.message.reply_text(
        "Welcome. Choose a role.\n\n" + await prefs_text(user.id),
        reply_markup=role_keyboard(prefs["role"] or DEFAULT_ROLE),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    await update.message.reply_text(
        "/start — configure filters\n"
        "/help — show help\n\n"
        "This version uses only Greenhouse and focuses on clean filtering."
    )


async def on_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = query.from_user.id
    role = query.data.split(":", 1)[1]
    await set_role(user_id, role)

    await query.edit_message_text(
        "Choose a role.\n\n" + await prefs_text(user_id),
        reply_markup=role_keyboard(role),
    )


async def go_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = query.from_user.id
    prefs = await get_user_preferences(user_id)

    await query.edit_message_text(
        "Choose a date range.\n\n" + await prefs_text(user_id),
        reply_markup=date_keyboard(prefs["date_range"] or DEFAULT_DATE_RANGE),
    )


async def on_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = query.from_user.id
    date_range = query.data.split(":", 1)[1]
    await set_date_range(user_id, date_range)

    await query.edit_message_text(
        "Choose a date range.\n\n" + await prefs_text(user_id),
        reply_markup=date_keyboard(date_range),
    )


async def go_companies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = query.from_user.id
    prefs = await get_user_preferences(user_id)

    await query.edit_message_text(
        "Choose companies.\n\n" + await prefs_text(user_id),
        reply_markup=companies_keyboard(prefs["companies"]),
    )


async def on_company(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = query.from_user.id
    board_token = query.data.split(":", 1)[1]
    await toggle_company(user_id, board_token)

    prefs = await get_user_preferences(user_id)
    await query.edit_message_text(
        "Choose companies.\n\n" + await prefs_text(user_id),
        reply_markup=companies_keyboard(prefs["companies"]),
    )


async def run_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = query.from_user.id
    prefs = await get_user_preferences(user_id)

    role = prefs["role"] or DEFAULT_ROLE
    date_range_raw = prefs["date_range"] or DEFAULT_DATE_RANGE
    board_tokens = sorted(prefs["companies"]) if prefs["companies"] else list(GREENHOUSE_BOARDS.keys())

    try:
        date_range_days = int(date_range_raw)
    except ValueError:
        date_range_days = 7

    await query.edit_message_text("Searching jobs...")

    jobs = await fetch_jobs_for_boards(board_tokens)
    filtered = filter_jobs(jobs, role, date_range_days)

    if not filtered:
        await context.bot.send_message(
            chat_id=user_id,
            text="No jobs found for your current filters.",
        )
        return

    top_jobs = filtered[:MAX_RESULTS_PER_SEARCH]

    await context.bot.send_message(
        chat_id=user_id,
        text=f"Found {len(filtered)} matching jobs. Showing first {len(top_jobs)}.",
    )

    for i, job in enumerate(top_jobs, start=1):
        await context.bot.send_message(
            chat_id=user_id,
            text=format_job(i, job),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def post_init(application: Application) -> None:
    await init_db()


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    app = Application.builder().token(token).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CallbackQueryHandler(on_role, pattern=r"^role:"))
    app.add_handler(CallbackQueryHandler(go_date, pattern=r"^go:date$"))
    app.add_handler(CallbackQueryHandler(on_date, pattern=r"^date:"))
    app.add_handler(CallbackQueryHandler(go_companies, pattern=r"^go:companies$"))
    app.add_handler(CallbackQueryHandler(on_company, pattern=r"^company:"))
    app.add_handler(CallbackQueryHandler(run_search, pattern=r"^run:search$"))

    logger.info("Bot starting")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

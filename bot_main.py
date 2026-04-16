import asyncio
import logging
import os
from datetime import datetime, timezone
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

from filters import apply_filters
from parsers_greenhouse import parse_greenhouse
from parsers_lever import parse_lever
from parsers_ashby import parse_ashby
from parsers_smartrecruiters import parse_smartrecruiters

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

user_preferences: dict[int, dict] = {}

POSITIONS = {
    "developer": "Разработчик 👨‍💻",
    "designer": "Дизайнер 🎨",
    "content": "Контент ✍️",
    "marketing": "Маркетинг 📣",
    "product": "Product 📦",
    "hr": "HR 👥",
    "community": "Community 🌍",
    "trader": "Trader / Research 📈",
}

FORMATS = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "freelance": "Freelance / Contract",
    "internship": "Internship",
}

SOURCES = {
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "ashby": "Ashby",
    "smartrecruiters": "SmartRecruiters",
}

DATE_RANGES = {
    "1": "Сегодня",
    "3": "За 3 дня",
    "7": "За 7 дней",
    "30": "За 30 дней",
    "all": "За всё время",
}


def get_user_prefs(user_id: int) -> dict:
    if user_id not in user_preferences:
        user_preferences[user_id] = {
            "positions": set(),
            "formats": set(),
            "sources": set(SOURCES.keys()),
            "date_range": "7",
        }
    return user_preferences[user_id]


def build_position_keyboard(user_id: int) -> InlineKeyboardMarkup:
    prefs = get_user_prefs(user_id)
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if key in prefs['positions'] else '☐ '}{label}",
                callback_data=f"pos_{key}",
            )
        ]
        for key, label in POSITIONS.items()
    ]
    keyboard.append([InlineKeyboardButton("➡️ Дальше: формат", callback_data="step_format")])
    return InlineKeyboardMarkup(keyboard)


def build_format_keyboard(user_id: int) -> InlineKeyboardMarkup:
    prefs = get_user_prefs(user_id)
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if key in prefs['formats'] else '☐ '}{label}",
                callback_data=f"fmt_{key}",
            )
        ]
        for key, label in FORMATS.items()
    ]
    keyboard.append([InlineKeyboardButton("➡️ Дальше: источники", callback_data="step_sources")])
    return InlineKeyboardMarkup(keyboard)


def build_sources_keyboard(user_id: int) -> InlineKeyboardMarkup:
    prefs = get_user_prefs(user_id)
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if key in prefs['sources'] else '☐ '}{label}",
                callback_data=f"src_{key}",
            )
        ]
        for key, label in SOURCES.items()
    ]
    keyboard.append([InlineKeyboardButton("➡️ Дальше: дата", callback_data="step_dates")])
    return InlineKeyboardMarkup(keyboard)


def build_dates_keyboard(user_id: int) -> InlineKeyboardMarkup:
    prefs = get_user_prefs(user_id)
    current = prefs["date_range"]

    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if key == current else '☐ '}{label}",
                callback_data=f"date_{key}",
            )
        ]
        for key, label in DATE_RANGES.items()
    ]
    keyboard.append([InlineKeyboardButton("🚀 Искать вакансии", callback_data="start_search")])
    return InlineKeyboardMarkup(keyboard)


def format_prefs_summary(user_id: int) -> str:
    prefs = get_user_prefs(user_id)

    positions = ", ".join(POSITIONS[p] for p in prefs["positions"]) or "не выбрано"
    formats = ", ".join(FORMATS[f] for f in prefs["formats"]) or "любой"
    sources = ", ".join(SOURCES[s] for s in prefs["sources"]) or "не выбрано"
    date_range = DATE_RANGES.get(prefs["date_range"], "не выбрано")

    return (
        f"Текущие фильтры:\n"
        f"• Позиции: {positions}\n"
        f"• Формат: {formats}\n"
        f"• Источники: {sources}\n"
        f"• Период: {date_range}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    get_user_prefs(user_id)

    await update.message.reply_text(
        "Привет! Выбери должности:\n\n" + format_prefs_summary(user_id),
        reply_markup=build_position_keyboard(user_id),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/start — настроить поиск\n"
        "/help — справка\n\n"
        "Фильтры: должности, формат, источники, даты."
    )


async def on_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    value = query.data.removeprefix("pos_")
    prefs = get_user_prefs(user_id)

    if value in prefs["positions"]:
        prefs["positions"].remove(value)
    else:
        prefs["positions"].add(value)

    await query.edit_message_text(
        "Выбери должности:\n\n" + format_prefs_summary(user_id),
        reply_markup=build_position_keyboard(user_id),
    )


async def go_step_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    await query.edit_message_text(
        "Выбери формат:\n\n" + format_prefs_summary(user_id),
        reply_markup=build_format_keyboard(user_id),
    )


async def on_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    value = query.data.removeprefix("fmt_")
    prefs = get_user_prefs(user_id)

    if value in prefs["formats"]:
        prefs["formats"].remove(value)
    else:
        prefs["formats"].add(value)

    await query.edit_message_text(
        "Выбери формат:\n\n" + format_prefs_summary(user_id),
        reply_markup=build_format_keyboard(user_id),
    )


async def go_step_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    await query.edit_message_text(
        "Выбери источники:\n\n" + format_prefs_summary(user_id),
        reply_markup=build_sources_keyboard(user_id),
    )


async def on_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    value = query.data.removeprefix("src_")
    prefs = get_user_prefs(user_id)

    if value in prefs["sources"]:
        prefs["sources"].remove(value)
    else:
        prefs["sources"].add(value)

    await query.edit_message_text(
        "Выбери источники:\n\n" + format_prefs_summary(user_id),
        reply_markup=build_sources_keyboard(user_id),
    )


async def go_step_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    await query.edit_message_text(
        "Выбери период:\n\n" + format_prefs_summary(user_id),
        reply_markup=build_dates_keyboard(user_id),
    )


async def on_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    value = query.data.removeprefix("date_")
    prefs = get_user_prefs(user_id)
    prefs["date_range"] = value

    await query.edit_message_text(
        "Выбери период:\n\n" + format_prefs_summary(user_id),
        reply_markup=build_dates_keyboard(user_id),
    )


def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    seen = set()
    result = []

    for job in jobs:
        key = (
            (job.get("url") or "").strip().lower(),
            (job.get("title") or "").strip().lower(),
            (job.get("company") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(job)

    return result


def sort_jobs_by_date(jobs: list[dict]) -> list[dict]:
    def parse_dt(value: str):
        if not value:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    return sorted(jobs, key=lambda x: parse_dt(x.get("posted_at", "")), reverse=True)


def format_job_message(index: int, job: dict) -> str:
    title = escape(job.get("title", "N/A"))
    company = escape(job.get("company", "N/A"))
    location = escape(job.get("location", "N/A"))
    salary = escape(job.get("salary", "Не указана"))
    job_format = escape(job.get("format", "N/A"))
    source = escape(job.get("source", "N/A"))
    url = escape(job.get("url", ""))
    posted_at = escape(job.get("posted_at_human", "Не указана"))
    detected_role = escape(job.get("detected_role", "unknown"))

    lines = [
        f"<b>{index}. {title}</b>",
        f"🏢 {company}",
        f"📍 {location}",
        f"💼 {job_format}",
        f"💰 {salary}",
        f"🕒 {posted_at}",
        f"🏷 Роль: {detected_role}",
        f"🔎 Источник: {source}",
    ]

    if url:
        lines.append(f'🔗 <a href="{url}">Ссылка на вакансию</a>')

    return "\n".join(lines)


async def gather_jobs(selected_sources: set[str]) -> list[dict]:
    tasks = []

    if "greenhouse" in selected_sources:
        tasks.append(parse_greenhouse())
    if "lever" in selected_sources:
        tasks.append(parse_lever())
    if "ashby" in selected_sources:
        tasks.append(parse_ashby())
    if "smartrecruiters" in selected_sources:
        tasks.append(parse_smartrecruiters())

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)

    jobs = []
    for result in results:
        if isinstance(result, Exception):
            logger.exception("Source parser failed: %s", result)
            continue
        jobs.extend(result)

    return jobs


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    prefs = get_user_prefs(user_id)

    if not prefs["positions"]:
        await query.edit_message_text("⚠️ Выбери хотя бы одну должность.")
        return

    if not prefs["sources"]:
        await query.edit_message_text("⚠️ Выбери хотя бы один источник.")
        return

    await query.edit_message_text(
        "🔎 Ищу вакансии...\n"
        "⏳ Собираю данные из источников и фильтрую более точно."
    )

    try:
        jobs = await gather_jobs(prefs["sources"])
        logger.info("Fetched jobs before dedupe: %s", len(jobs))

        jobs = dedupe_jobs(jobs)
        jobs = sort_jobs_by_date(jobs)

        filtered_jobs = apply_filters(jobs, prefs)
        logger.info("Jobs after filters: %s", len(filtered_jobs))

        if not filtered_jobs:
            await context.bot.send_message(
                chat_id=user_id,
                text="😔 По выбранным фильтрам вакансий не найдено.",
            )
            return

        top_jobs = filtered_jobs[:20]

        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Найдено {len(filtered_jobs)} вакансий. Показываю первые {len(top_jobs)}.",
        )

        for i, job in enumerate(top_jobs, start=1):
            await context.bot.send_message(
                chat_id=user_id,
                text=format_job_message(i, job),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            await asyncio.sleep(0.15)

    except Exception:
        logger.exception("Search failed")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Ошибка при поиске вакансий. Посмотри логи.",
        )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CallbackQueryHandler(on_position, pattern=r"^pos_"))
    app.add_handler(CallbackQueryHandler(go_step_format, pattern=r"^step_format$"))
    app.add_handler(CallbackQueryHandler(on_format, pattern=r"^fmt_"))
    app.add_handler(CallbackQueryHandler(go_step_sources, pattern=r"^step_sources$"))
    app.add_handler(CallbackQueryHandler(on_source, pattern=r"^src_"))
    app.add_handler(CallbackQueryHandler(go_step_dates, pattern=r"^step_dates$"))
    app.add_handler(CallbackQueryHandler(on_date, pattern=r"^date_"))
    app.add_handler(CallbackQueryHandler(start_search, pattern=r"^start_search$"))

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

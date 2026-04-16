import asyncio
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

from filters import apply_filters
from parsers_greenhouse import parse_greenhouse


load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

user_preferences: dict[int, dict[str, set[str]]] = {}

POSITIONS = {
    "developer": "Разработчик 👨‍💻",
    "designer": "Дизайнер 🎨",
    "content": "Контент-мейкер ✍️",
    "marketing": "Маркетолог 📣",
    "product": "Product Manager 📦",
    "hr": "HR 👥",
    "community": "Community Manager 🌍",
    "trader": "Трейдер 📈",
}

FORMATS = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "freelance": "Фриланс",
    "internship": "Стажировка",
}


def get_user_prefs(user_id: int) -> dict[str, set[str]]:
    if user_id not in user_preferences:
        user_preferences[user_id] = {"positions": set(), "formats": set()}
    return user_preferences[user_id]


def build_position_keyboard(user_id: int) -> InlineKeyboardMarkup:
    prefs = get_user_prefs(user_id)
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if key in prefs['positions'] else '☐ '}{name}",
                callback_data=f"pos_{key}",
            )
        ]
        for key, name in POSITIONS.items()
    ]
    keyboard.append([InlineKeyboardButton("➡️ Дальше", callback_data="next_format")])
    return InlineKeyboardMarkup(keyboard)


def build_format_keyboard(user_id: int) -> InlineKeyboardMarkup:
    prefs = get_user_prefs(user_id)
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if key in prefs['formats'] else '☐ '}{name}",
                callback_data=f"fmt_{key}",
            )
        ]
        for key, name in FORMATS.items()
    ]
    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="start_search")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    get_user_prefs(user_id)

    await update.message.reply_text(
        "Привет! Выбери должность:",
        reply_markup=build_position_keyboard(user_id),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Crypto Jobs Bot\n\n"
        "/start — начать поиск\n"
        "/help — справка"
    )


async def select_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    position = query.data.removeprefix("pos_")
    prefs = get_user_prefs(user_id)

    if position in prefs["positions"]:
        prefs["positions"].remove(position)
    else:
        prefs["positions"].add(position)

    selected = ", ".join(POSITIONS[p] for p in prefs["positions"]) or "ничего"

    await query.edit_message_text(
        f"Выбрано: {selected}",
        reply_markup=build_position_keyboard(user_id),
    )


async def show_formats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    await query.edit_message_text(
        "Выбери формат:",
        reply_markup=build_format_keyboard(user_id),
    )


async def select_format_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    fmt = query.data.removeprefix("fmt_")  # фикс бага fmt_full_time -> full_time
    prefs = get_user_prefs(user_id)

    if fmt in prefs["formats"]:
        prefs["formats"].remove(fmt)
    else:
        prefs["formats"].add(fmt)

    selected = ", ".join(FORMATS[f] for f in prefs["formats"]) or "любой"

    await query.edit_message_text(
        f"Выбрано: {selected}",
        reply_markup=build_format_keyboard(user_id),
    )


def format_job_message(index: int, job: dict) -> str:
    title = escape(job.get("title", "N/A"))
    company = escape(job.get("company", "N/A"))
    salary = escape(job.get("salary", "Не указана"))
    location = escape(job.get("location", "N/A"))
    job_format = escape(job.get("format", "N/A"))
    source = escape(job.get("source", "Unknown"))
    url = escape(job.get("url", ""))

    lines = [
        f"<b>{index}. {title}</b>",
        f"🏢 {company}",
        f"📍 {location}",
        f"💼 {job_format}",
        f"💰 {salary}",
        f"🔎 Источник: {source}",
    ]

    if url:
        lines.append(f'🔗 <a href="{url}">Ссылка на вакансию</a>')

    return "\n".join(lines)


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    prefs = get_user_prefs(user_id)

    if not prefs["positions"]:
        await query.edit_message_text("⚠️ Выбери хотя бы одну должность!")
        return

    await query.edit_message_text("🔎 Ищу вакансии...\n⏳ Подожди немного...")

    try:
        jobs: list[dict] = []

        logger.info("Parsing Greenhouse jobs for user_id=%s", user_id)
        gh_jobs = await parse_greenhouse()
        logger.info("Greenhouse returned %s jobs", len(gh_jobs))
        jobs.extend(gh_jobs)

        logger.info("Total jobs before filtering: %s", len(jobs))
        filtered_jobs = apply_filters(jobs, prefs)
        logger.info("Jobs after filtering: %s", len(filtered_jobs))

        if not filtered_jobs:
            await context.bot.send_message(
                chat_id=user_id,
                text="😔 К сожалению, вакансий не найдено по твоим критериям.",
            )
            return

        top_jobs = filtered_jobs[:10]
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Найдено {len(top_jobs)} вакансий:",
        )

        for i, job in enumerate(top_jobs, start=1):
            message = format_job_message(i, job)
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            await asyncio.sleep(0.3)

        logger.info("Sent %s jobs to user_id=%s", len(top_jobs), user_id)

    except Exception:
        logger.exception("Search error")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Ошибка при поиске вакансий. Проверь логи.",
        )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(select_position, pattern=r"^pos_"))
    app.add_handler(CallbackQueryHandler(show_formats, pattern=r"^next_format$"))
    app.add_handler(CallbackQueryHandler(select_format_callback, pattern=r"^fmt_"))
    app.add_handler(CallbackQueryHandler(start_search, pattern=r"^start_search$"))

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

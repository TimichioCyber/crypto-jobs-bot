"""
Crypto Jobs Telegram Bot — FIXED VERSION
Парсит вакансии с сайтов и каналов, отправляет в Telegram с фильтрацией
"""

import asyncio
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, JobQueue
import json
from datetime import datetime

try:
    from parsers_cryptojobs import parse_cryptojobs
except ImportError:
    async def parse_cryptojobs():
        return []

try:
    from parsers_angellist import parse_angellist
except ImportError:
    async def parse_angellist():
        return []

try:
    from parsers_greenhouse import parse_greenhouse
except ImportError:
    async def parse_greenhouse():
        return []

try:
    from filters import apply_filters
except ImportError:
    def apply_filters(jobs, prefs):
        return jobs

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Хранилище юзер-фильтров
user_preferences = {}

# Доступные должности
POSITIONS = {
    'developer': 'Разработчик 👨‍💻',
    'designer': 'Дизайнер 🎨',
    'content': 'Контент-мейкер ✍️',
    'marketing': 'Маркетолог 📢',
    'product': 'Product Manager 📊',
    'hr': 'HR 👥',
    'community': 'Community Manager 💬',
    'trader': 'Трейдер 📈',
}

FORMATS = {
    'full_time': 'Full-time',
    'part_time': 'Part-time',
    'freelance': 'Фриланс',
    'internship': 'Стажировка',
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started bot")

    keyboard = []
    for position_key, position_name in POSITIONS.items():
        keyboard.append([InlineKeyboardButton(position_name, callback_data=f'pos_{position_key}')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Привет! Я ищу крипто-вакансии для тебя.\n\n"
        "Выбери интересующие должности (можешь несколько):",
        reply_markup=reply_markup
    )

async def select_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выбор должности"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    position = query.data.split('_')[1]

    if user_id not in user_preferences:
        user_preferences[user_id] = {
            'positions': set(),
            'formats': set(),
            'min_salary': None,
            'countries': set(),
        }

    if position in user_preferences[user_id]['positions']:
        user_preferences[user_id]['positions'].discard(position)
    else:
        user_preferences[user_id]['positions'].add(position)

    selected = ', '.join([POSITIONS[p] for p in user_preferences[user_id]['positions']])

    keyboard = []
    for position_key, position_name in POSITIONS.items():
        prefix = '✅ ' if position_key in user_preferences[user_id]['positions'] else '☐ '
        keyboard.append([InlineKeyboardButton(f"{prefix}{position_name}", callback_data=f'pos_{position_key}')])

    keyboard.append([InlineKeyboardButton('➡️ Дальше', callback_data='next_format')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"📍 Выбрано: {selected if selected else 'ничего'}\n\nВыбери ещё, если нужно:"

    await query.edit_message_text(text, reply_markup=reply_markup)

async def select_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выбор формата работы"""
    query = update.callback_query
    await query.answer()

    keyboard = []
    for format_key, format_name in FORMATS.items():
        keyboard.append([InlineKeyboardButton(format_name, callback_data=f'fmt_{format_key}')])

    keyboard.append([InlineKeyboardButton('✅ Готово', callback_data='start_search')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📋 Выбери формат работы (можешь несколько):",
        reply_markup=reply_markup
    )

async def select_format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора формата"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    format_type = query.data.split('_')[1]

    if user_id not in user_preferences:
        user_preferences[user_id] = {'positions': set(), 'formats': set(), 'min_salary': None, 'countries': set()}

    if format_type in user_preferences[user_id]['formats']:
        user_preferences[user_id]['formats'].discard(format_type)
    else:
        user_preferences[user_id]['formats'].add(format_type)

    selected = ', '.join([FORMATS[f] for f in user_preferences[user_id]['formats']])

    keyboard = []
    for format_key, format_name in FORMATS.items():
        prefix = '✅ ' if format_key in user_preferences[user_id]['formats'] else '☐ '
        keyboard.append([InlineKeyboardButton(f"{prefix}{format_name}", callback_data=f'fmt_{format_key}')])

    keyboard.append([InlineKeyboardButton('✅ Готово', callback_data='start_search')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"📋 Выбрано: {selected if selected else 'любой'}\n\nВыбери ещё, если нужно:"

    await query.edit_message_text(text, reply_markup=reply_markup)

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начало поиска"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id not in user_preferences or not user_preferences[user_id]['positions']:
        await query.edit_message_text("⚠️ Выбери хотя бы одну должность!")
        return

    logger.info(f"User {user_id} started search for positions: {user_preferences[user_id]['positions']}")

    await query.edit_message_text(
        "🔍 Начинаю поиск вакансий...\n"
        "Буду присылать результаты каждый час\n\n"
        "Команды:\n"
        "/help - справка"
    )

    # Запускаем поиск в фоне
    try:
        context.job_queue.run_repeating(
            search_and_send,
            interval=3600,
            first=15,
            context=user_id,
            name=f"search_{user_id}"
        )
    except Exception as e:
        logger.error(f"Error scheduling job: {e}")
        await context.bot.send_message(user_id, f"❌ Ошибка при запуске поиска: {str(e)}")

async def search_and_send(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Поиск и отправка вакансий"""
    user_id = context.job.context
    logger.info(f"Searching vacancies for user {user_id}")

    try:
        jobs = []

        # Парсим источники
        try:
            jobs.extend(await parse_cryptojobs())
        except Exception as e:
            logger.error(f"Error parsing CryptoJobs: {e}")

        try:
            jobs.extend(await parse_angellist())
        except Exception as e:
            logger.error(f"Error parsing AngelList: {e}")

        try:
            jobs.extend(await parse_greenhouse())
        except Exception as e:
            logger.error(f"Error parsing Greenhouse: {e}")

        # Фильтруем
        filtered_jobs = apply_filters(jobs, user_preferences.get(user_id, {}))

        if not filtered_jobs:
            await context.bot.send_message(user_id, "😴 Новых вакансий не найдено")
            return

        # Отправляем
        count = 0
        for job in filtered_jobs[:10]:
            try:
                message = format_job_message(job)
                await context.bot.send_message(user_id, message, parse_mode='HTML')
                count += 1
            except Exception as e:
                logger.error(f"Error sending job: {e}")

        logger.info(f"Sent {count} vacancies to user {user_id}")

    except Exception as e:
        logger.error(f"Error in search_and_send: {e}")

def format_job_message(job: dict) -> str:
    """Форматирование вакансии"""
    return f"""
<b>{job.get('title', 'N/A')}</b>
🏢 {job.get('company', 'N/A')}

💰 {job.get('salary', 'Не указана')}
📍 {job.get('location', 'N/A')}
💼 {job.get('format', 'N/A')}

<i>{job.get('description', '')[:200]}...</i>

<a href="{job.get('url', '#')}">Подробнее →</a>
"""

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Справка"""
    help_text = """
🤖 <b>Crypto Jobs Bot</b>

Я ищу вакансии в крипто-сфере и отправляю их тебе в Telegram.

<b>Команды:</b>
/start - Начать, выбрать должность
/help - Эта справка

<b>Источники:</b>
- CryptoJobs.com
- AngelList
- Greenhouse

Вакансии обновляются каждый час!
    """
    await update.message.reply_text(help_text, parse_mode='HTML')

def main():
    """Запуск бота"""
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        raise ValueError("Установи TELEGRAM_BOT_TOKEN!")

    # Создаём приложение с job queue
    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(select_position, pattern='^pos_'))
    application.add_handler(CallbackQueryHandler(select_format, pattern='^next_format'))
    application.add_handler(CallbackQueryHandler(select_format_callback, pattern='^fmt_'))
    application.add_handler(CallbackQueryHandler(start_search, pattern='^start_search'))

    logger.info("Bot started")

    # Запускаем
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

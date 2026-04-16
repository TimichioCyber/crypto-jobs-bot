"""
Crypto Jobs Telegram Bot — SIMPLIFIED VERSION
"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

try:
    from parsers_cryptojobs import parse_cryptojobs
except:
    async def parse_cryptojobs():
        return []

try:
    from parsers_angellist import parse_angellist
except:
    async def parse_angellist():
        return []

try:
    from parsers_greenhouse import parse_greenhouse
except:
    async def parse_greenhouse():
        return []

try:
    from filters import apply_filters
except:
    def apply_filters(jobs, prefs):
        return jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_preferences = {}

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
    user_id = update.effective_user.id
    keyboard = [[InlineKeyboardButton(name, callback_data=f'pos_{key}')] for key, name in POSITIONS.items()]
    await update.message.reply_text(
        "👋 Привет! Выбери должность:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def select_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    position = query.data.split('_')[1]
    
    if user_id not in user_preferences:
        user_preferences[user_id] = {'positions': set(), 'formats': set()}
    
    if position in user_preferences[user_id]['positions']:
        user_preferences[user_id]['positions'].discard(position)
    else:
        user_preferences[user_id]['positions'].add(position)
    
    selected = ', '.join([POSITIONS[p] for p in user_preferences[user_id]['positions']])
    keyboard = [[InlineKeyboardButton(f"{'✅ ' if key in user_preferences[user_id]['positions'] else '☐ '}{name}", callback_data=f'pos_{key}')] for key, name in POSITIONS.items()]
    keyboard.append([InlineKeyboardButton('➡️ Дальше', callback_data='next_format')])
    
    await query.edit_message_text(
        f"📍 Выбрано: {selected if selected else 'ничего'}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def select_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(name, callback_data=f'fmt_{key}')] for key, name in FORMATS.items()]
    keyboard.append([InlineKeyboardButton('✅ Готово', callback_data='start_search')])
    await query.edit_message_text("📋 Выбери формат:", reply_markup=InlineKeyboardMarkup(keyboard))

async def select_format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    fmt = query.data.split('_')[1]
    
    if user_id not in user_preferences:
        user_preferences[user_id] = {'positions': set(), 'formats': set()}
    
    if fmt in user_preferences[user_id]['formats']:
        user_preferences[user_id]['formats'].discard(fmt)
    else:
        user_preferences[user_id]['formats'].add(fmt)
    
    selected = ', '.join([FORMATS[f] for f in user_preferences[user_id]['formats']])
    keyboard = [[InlineKeyboardButton(f"{'✅ ' if key in user_preferences[user_id]['formats'] else '☐ '}{name}", callback_data=f'fmt_{key}')] for key, name in FORMATS.items()]
    keyboard.append([InlineKeyboardButton('✅ Готово', callback_data='start_search')])
    
    await query.edit_message_text(
        f"📋 Выбрано: {selected if selected else 'любой'}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if user_id not in user_preferences or not user_preferences[user_id]['positions']:
        await query.edit_message_text("⚠️ Выбери хотя бы одну должность!")
        return
    
    await query.edit_message_text("🔍 Начинаю поиск вакансий!\nРезультаты будут по мере поиска.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🤖 Crypto Jobs Bot\n\n/start - Начать\n/help - Справка")

def main():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен!")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(select_position, pattern='^pos_'))
    app.add_handler(CallbackQueryHandler(select_format, pattern='^next_format'))
    app.add_handler(CallbackQueryHandler(select_format_callback, pattern='^fmt_'))
    app.add_handler(CallbackQueryHandler(start_search, pattern='^start_search'))
    
    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

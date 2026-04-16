# Crypto Jobs Telegram Bot

Парсит крипто-вакансии из 6 ATS + собирает в Telegram с фильтрацией.

## ⚠️ Безопасность

**НИКОГДА** не коммитьте `.env` файл в GitHub!

- `.env` в `.gitignore` (уже добавлен)
- Токен хранится ТОЛЬКО в переменных окружения Railway
- `.env.example` — только шаблон с placeholder'ами

## 🚀 Быстрый старт

### Локально (для тестирования)

```bash
# 1. Клонируй репо
git clone <твой-репо>
cd crypto-jobs-bot

# 2. Установи зависимости
pip install -r requirements.txt

# 3. Создай .env (скопируй из .env.example)
cp .env.example .env
# Отредактируй .env, вставь свой TELEGRAM_BOT_TOKEN

# 4. Запусти бота
python bot_main.py
```

### Railway (продакшен)

1. **Создай переменные окружения в Railway:**
   - Dashboard → Variables
   - Добавь: `TELEGRAM_BOT_TOKEN` = `<твой_токен>`
   - Optional: `SEARCH_INTERVAL=3600` (по умолчанию уже есть)

2. **Коммитни в GitHub (БЕЗ .env):**
   ```bash
   git add .
   git commit -m "crypto jobs bot"
   git push
   ```

3. **Railway подхватит автоматически** (Procfile есть, requirements.txt есть)

## 📋 Структура

```
.
├── bot_main.py                  # Основной бот (命令, кнопки, SQLite)
├── filters.py                   # Фильтрация вакансий
├── parsers_*.py                 # 6 парсеров (Greenhouse, Lever, Ashby, SmartRecruiters, CryptoJobs, AngelList)
├── requirements.txt             # Зависимости
├── Procfile                      # Railway process type
├── runtime.txt                   # Python версия
├── .env.example                  # Шаблон переменных (БЕЗ реальных значений!)
├── .gitignore                    # Исключи .env, *.db, __pycache__
└── README.md                     # Этот файл
```

## 🔧 Команды бота

- `/start` — первичная настройка фильтров
- `/status` — текущие фильтры
- `/pause` — пауза поиска (но бот остаётся включённым)
- `/resume` — возобновить поиск
- `/stop` — остановить поиск полностью
- `/help` — справка

## 📊 Источники вакансий

- **Greenhouse**: Coinbase, Kraken, OpenSea, Circle, Consensys, Fireblocks…
- **Lever**: Chainlink, Solana, DFINITY, MoonPay, Polygon, Avalanche…
- **Ashby**: Worldcoin, Risc Zero, Succinct, Ethena, Flashbots…
- **SmartRecruiters**: Binance, OKX, Bybit
- **CryptoJobs**: RSS-фид cryptojobslist.com
- **AngelList**: отключён (Cloudflare) — используй ATS выше

## 🎯 Фильтры

**Должности** (можно выбрать несколько):
- Разработчик, Дизайнер, Контент, Маркетолог, Product Manager, HR, Community, Трейдер, Аналитик, BD

**Формат** (опционально):
- Full-time, Part-time, Фриланс, Стажировка, Remote

**Период** (обязательно):
- За сутки, за 3 дня, за неделю, за месяц, за всё время

## 🔄 Как работает

1. **Юзер** вводит фильтры в боте → сохраняется в SQLite
2. **Фоновый цикл** каждый час (или `SEARCH_INTERVAL`):
   - Параллельно гонит 6 парсеров
   - Дедупирует по URL
   - Фильтрует по должности / формату / дате
   - Отправляет в Telegram (макс 10 за раз)
3. **При рестарте** всё восстанавливается из БД

## 🐛 Если что-то не работает

**Railway:**
```
Railway UI → View Logs
```

Ищи ошибки от парсеров (они логируют всё).

**Локально:**
```bash
python bot_main.py
# Сразу видишь логи в консоли
```

## 📦 Переменные окружения (Railway)

| Переменная | Значение | Обязательно |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | токен от BotFather | ✅ Да |
| `SEARCH_INTERVAL` | сек между поисками (default: 3600) | ❌ Нет |
| `MAX_PER_BATCH` | макс вакансий за раз (default: 10) | ❌ Нет |
| `DB_PATH` | путь к .db файлу (default: bot.db) | ❌ Нет |

## 📝 Заметки

- Каждый парсер имеет timeout 15 сек (не зависает)
- Дедуп по URL → одна вакансия максимум один раз пользователю
- SQLite → персистентные фильтры даже после крашей
- Async + asyncio.gather → все парсеры в параллель

---

Готово к деплою. Коммитни в GitHub, Railway подхватит 🚀

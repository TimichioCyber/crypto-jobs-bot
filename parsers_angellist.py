"""
Wellfound (бывший AngelList) parser.
Публичного API у них нет, поэтому используем их собственный RSS (если есть)
или парсим HTML страницы remote-crypto-jobs.

Fallback: возвращаем пустой список (чтобы бот не падал).
"""
import logging
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URLS = [
    "https://wellfound.com/role/r/blockchain-engineer",
    "https://wellfound.com/role/r/crypto",
]

TIMEOUT = aiohttp.ClientTimeout(total=15)
HEADERS = {"User-Agent": "Mozilla/5.0 (crypto-jobs-bot)"}


async def parse_angellist() -> list[dict]:
    """
    Wellfound сильно защищён от скрейпа (Cloudflare, JS-rendering).
    Возвращаем [] — основной поток вакансий идёт через ATS.
    Можно заменить на парсинг через headless browser, если понадобится.
    """
    logger.info("AngelList/Wellfound: skipped (JS-protected, use ATS parsers instead)")
    return []

"""
CryptoJobs parser — скрейпит cryptojobslist.com через публичный RSS/JSON.
Fallback: HTML-скрейп через BeautifulSoup.
"""
import logging
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FEED_URL = "https://cryptojobslist.com/rss"
TIMEOUT = aiohttp.ClientTimeout(total=15)
HEADERS = {"User-Agent": "Mozilla/5.0 (crypto-jobs-bot)"}


async def parse_cryptojobs() -> list[dict]:
    jobs: list[dict] = []
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
            async with session.get(FEED_URL) as resp:
                if resp.status != 200:
                    logger.warning(f"CryptoJobs RSS: HTTP {resp.status}")
                    return []
                xml = await resp.text()

        soup = BeautifulSoup(xml, "xml")
        for item in soup.find_all("item")[:80]:
            try:
                title_full = item.title.text if item.title else ""
                link = item.link.text if item.link else ""
                pub = item.pubDate.text if item.pubDate else ""
                desc = (item.description.text if item.description else "")[:400]

                # Формат RSS: "Role at Company" — пытаемся распарсить
                company = ""
                title = title_full
                if " at " in title_full:
                    parts = title_full.rsplit(" at ", 1)
                    title = parts[0].strip()
                    company = parts[1].strip()

                jobs.append({
                    "title": title,
                    "company": company or "—",
                    "location": "Remote",
                    "format": "Full-time",
                    "salary": "Не указана",
                    "description": desc,
                    "url": link,
                    "source": "CryptoJobsList",
                    "posted_at_rfc": pub,
                })
            except Exception as e:
                logger.debug(f"CryptoJobs parse item fail: {e}")
    except Exception as e:
        logger.warning(f"CryptoJobs fetch fail: {e}")

    logger.info(f"CryptoJobs: {len(jobs)} jobs")
    return jobs

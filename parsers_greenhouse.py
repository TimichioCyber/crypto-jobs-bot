"""
Greenhouse ATS parser — тянет вакансии через публичный JSON API.
Каждая компания на Greenhouse имеет endpoint: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
"""
import asyncio
import logging
from datetime import datetime, timezone
import aiohttp

logger = logging.getLogger(__name__)

# Список крипто-компаний на Greenhouse (slug на boards.greenhouse.io)
COMPANIES = [
    ("Coinbase", "coinbase"),
    ("Kraken", "kraken"),
    ("OpenSea", "opensea"),
    ("Circle", "circle"),
    ("Consensys", "consensys"),
    ("Fireblocks", "fireblocks"),
    ("Gemini", "gemini"),
    ("Ripple", "ripple"),
    ("Blockchain.com", "blockchain"),
    ("Paradigm", "paradigm1"),
    ("Offchain Labs", "offchainlabs"),
    ("Uniswap Labs", "uniswaplabs"),
    ("Alchemy", "alchemy"),
    ("Anchorage", "anchorage"),
    ("dYdX", "dydxtrading"),
]

TIMEOUT = aiohttp.ClientTimeout(total=15)


async def _fetch_company(session: aiohttp.ClientSession, name: str, slug: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning(f"Greenhouse {name}: HTTP {resp.status}")
                return []
            data = await resp.json()
    except Exception as e:
        logger.warning(f"Greenhouse {name}: {e}")
        return []

    jobs = []
    for item in data.get("jobs", []):
        try:
            title = item.get("title", "")
            location = (item.get("location") or {}).get("name", "Remote")
            job_url = item.get("absolute_url", "")
            updated = item.get("updated_at") or item.get("first_published")
            content = (item.get("content") or "")[:400].replace("\n", " ").strip()

            jobs.append({
                "title": title,
                "company": name,
                "location": location,
                "format": _guess_format(title, location),
                "salary": "Не указана",
                "description": content,
                "url": job_url,
                "source": "Greenhouse",
                "posted_at": updated,
            })
        except Exception as e:
            logger.debug(f"Greenhouse parse item fail: {e}")
    return jobs


def _guess_format(title: str, location: str) -> str:
    t = (title + " " + location).lower()
    if "intern" in t:
        return "Стажировка"
    if "contract" in t or "freelance" in t:
        return "Фриланс"
    if "part-time" in t or "part time" in t:
        return "Part-time"
    if "remote" in t:
        return "Remote / Full-time"
    return "Full-time"


async def parse_greenhouse() -> list[dict]:
    all_jobs: list[dict] = []
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        tasks = [_fetch_company(session, name, slug) for name, slug in COMPANIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_jobs.extend(r)
    logger.info(f"Greenhouse: total {len(all_jobs)} jobs")
    return all_jobs

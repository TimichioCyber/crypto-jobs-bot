"""
Lever ATS parser — публичный JSON API: https://api.lever.co/v0/postings/{slug}
"""
import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

COMPANIES = [
    ("Chainlink Labs", "chainlink"),
    ("Solana Foundation", "solana"),
    ("DFINITY", "dfinity"),
    ("MoonPay", "moonpay"),
    ("Anchorage Digital", "anchorage"),
    ("BitGo", "bitgo"),
    ("Polygon", "polygontechnology"),
    ("Avalanche / Ava Labs", "avalabs"),
    ("Aragon", "aragon"),
    ("Mysten Labs", "mystenlabs"),
    ("Immutable", "immutable"),
    ("Matter Labs", "matterlabs"),
]

TIMEOUT = aiohttp.ClientTimeout(total=15)


async def _fetch_company(session: aiohttp.ClientSession, name: str, slug: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning(f"Lever {name}: HTTP {resp.status}")
                return []
            data = await resp.json()
    except Exception as e:
        logger.warning(f"Lever {name}: {e}")
        return []

    jobs = []
    for item in data:
        try:
            title = item.get("text", "")
            cats = item.get("categories") or {}
            location = cats.get("location", "Remote")
            commitment = cats.get("commitment", "")
            team = cats.get("team", "")
            job_url = item.get("hostedUrl") or item.get("applyUrl") or ""
            created = item.get("createdAt")  # ms epoch
            desc = (item.get("descriptionPlain") or item.get("description") or "")[:400].replace("\n", " ")

            jobs.append({
                "title": title,
                "company": name,
                "location": location,
                "format": _fmt(commitment, title, location),
                "salary": "Не указана",
                "description": f"{team}. {desc}".strip(" ."),
                "url": job_url,
                "source": "Lever",
                "posted_at_ms": created,
            })
        except Exception as e:
            logger.debug(f"Lever parse item fail: {e}")
    return jobs


def _fmt(commitment: str, title: str, location: str) -> str:
    c = (commitment or "").lower()
    t = (title + " " + location).lower()
    if "intern" in c or "intern" in t:
        return "Стажировка"
    if "part" in c:
        return "Part-time"
    if "contract" in c or "freelance" in c:
        return "Фриланс"
    if "remote" in t:
        return "Remote / Full-time"
    return "Full-time"


async def parse_lever() -> list[dict]:
    all_jobs: list[dict] = []
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        tasks = [_fetch_company(session, name, slug) for name, slug in COMPANIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_jobs.extend(r)
    logger.info(f"Lever: total {len(all_jobs)} jobs")
    return all_jobs

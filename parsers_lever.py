import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

LEVER_COMPANIES = {
    "chainlinklabs": "Chainlink Labs",
    "solanafoundation": "Solana Foundation",
    "dfinity": "DFINITY",
    "moonpay": "MoonPay",
    "anchorage": "Anchorage Digital",
    "bitgo": "BitGo",
    "polygon": "Polygon",
}

API_URL = "https://api.lever.co/v0/postings/{company}?mode=json"


def extract_location(job: dict[str, Any]) -> str:
    categories = job.get("categories") or {}
    return categories.get("location") or "Remote / Not specified"


def detect_format(job: dict[str, Any]) -> str:
    categories = job.get("categories") or {}
    commitment = (categories.get("commitment") or "").lower()
    title = (job.get("text") or "").lower()

    text = f"{commitment} {title}"

    if "intern" in text:
        return "internship"
    if "contract" in text or "freelance" in text:
        return "freelance"
    if "part time" in text or "part-time" in text:
        return "part_time"
    return "full_time"


def normalize_posted_at(created_at) -> str:
    if not created_at:
        return ""

    try:
        if isinstance(created_at, (int, float)):
            return datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).isoformat()
        return str(created_at)
    except Exception:
        return ""


async def fetch_company(session: aiohttp.ClientSession, company_slug: str, company_name: str) -> list[dict]:
    url = API_URL.format(company=company_slug)

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            text_preview = await resp.text()
            logger.info("Lever %s status=%s", company_slug, resp.status)

            if resp.status != 200:
                logger.warning("Lever %s bad response: %s", company_slug, text_preview[:200])
                return []

            data = await resp.json(content_type=None)
            jobs = []

            for job in data:
                jobs.append(
                    {
                        "title": (job.get("text") or "").strip(),
                        "company": company_name,
                        "location": extract_location(job),
                        "salary": "Не указана",
                        "format": detect_format(job),
                        "source": "lever",
                        "url": job.get("hostedUrl") or "",
                        "description": "",
                        "posted_at": normalize_posted_at(job.get("createdAt")),
                    }
                )

            return jobs

    except Exception as e:
        logger.warning("Lever parser failed for %s: %s", company_slug, e)
        return []


async def parse_lever() -> list[dict]:
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {"User-Agent": "Mozilla/5.0 (CryptoJobsBot/2.0)"}

    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = [
            fetch_company(session, slug, company)
            for slug, company in LEVER_COMPANIES.items()
        ]
        results = await asyncio.gather(*tasks)

    jobs = []
    for part in results:
        jobs.extend(part)

    return jobs

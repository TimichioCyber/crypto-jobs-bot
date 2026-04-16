import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

GREENHOUSE_BOARDS = {
    "coinbase": "Coinbase",
    "kraken": "Kraken",
    "chainalysis": "Chainalysis",
    "aave": "Aave",
    "opensea": "OpenSea",
    "alchemy": "Alchemy",
    "figure": "Figure",
    "consensys": "Consensys",
}

API_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def extract_location(job: dict[str, Any]) -> str:
    loc = job.get("location") or {}
    return loc.get("name") or "Remote / Not specified"


def detect_format(title: str, content: str = "") -> str:
    text = f"{title} {content}".lower()
    if any(x in text for x in ["intern", "internship", "стаж"]):
        return "internship"
    if any(x in text for x in ["contract", "freelance", "contractor"]):
        return "freelance"
    if any(x in text for x in ["part-time", "part time"]):
        return "part_time"
    return "full_time"


async def fetch_board(session: aiohttp.ClientSession, board: str, company: str) -> list[dict]:
    url = API_URL.format(board=board)

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            text_preview = await resp.text()
            logger.info("Greenhouse %s status=%s", board, resp.status)

            if resp.status != 200:
                logger.warning("Greenhouse %s bad response: %s", board, text_preview[:200])
                return []

            data = await resp.json(content_type=None)
            jobs = []

            for job in data.get("jobs", []):
                title = (job.get("title") or "").strip()
                content = (job.get("content") or "")[:1000]

                jobs.append(
                    {
                        "title": title,
                        "company": company,
                        "location": extract_location(job),
                        "salary": "Не указана",
                        "format": detect_format(title, content),
                        "source": "greenhouse",
                        "source_label": "Greenhouse",
                        "url": job.get("absolute_url", ""),
                        "description": content,
                        "posted_at": job.get("updated_at") or "",
                    }
                )

            return jobs

    except Exception as e:
        logger.warning("Greenhouse parser failed for %s: %s", board, e)
        return []


async def parse_greenhouse() -> list[dict]:
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {"User-Agent": "Mozilla/5.0 (CryptoJobsBot/2.0)"}

    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = [
            fetch_board(session, board, company)
            for board, company in GREENHOUSE_BOARDS.items()
        ]
        results = await asyncio.gather(*tasks)

    jobs = []
    for part in results:
        jobs.extend(part)
    return jobs

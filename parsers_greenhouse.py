import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# board_token -> company name
CRYPTO_GREENHOUSE_BOARDS = {
    "coinbase": "Coinbase",
    "kraken": "Kraken",
    "blockchain": "Blockchain.com",
    "opensea": "OpenSea",
    "aave": "Aave",
    "chainalysis": "Chainalysis",
}

GREENHOUSE_API_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def extract_location(job: dict[str, Any]) -> str:
    location = job.get("location") or {}
    name = location.get("name")
    if name:
        return name
    return "Remote / Not specified"


def extract_format(title: str, content: str = "") -> str:
    text = f"{title} {content}".lower()

    if any(word in text for word in ["intern", "internship", "стаж"]):
        return "internship"
    if any(word in text for word in ["contract", "freelance", "contractor"]):
        return "freelance"
    if any(word in text for word in ["part-time", "part time"]):
        return "part_time"
    return "full_time"


async def fetch_board_jobs(
    session: aiohttp.ClientSession, board_token: str, company_name: str
) -> list[dict]:
    url = GREENHOUSE_API_TEMPLATE.format(board=board_token)

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
            text_preview = await response.text()

            logger.info(
                "Greenhouse board=%s status=%s body_preview=%s",
                board_token,
                response.status,
                text_preview[:300].replace("\n", " "),
            )

            if response.status != 200:
                return []

            data = await response.json(content_type=None)
            jobs = []

            for job in data.get("jobs", []):
                title = job.get("title", "").strip()
                content = (job.get("content") or "")[:500]

                jobs.append(
                    {
                        "title": title,
                        "company": company_name,
                        "location": extract_location(job),
                        "salary": "Не указана",
                        "format": extract_format(title, content),
                        "description": content,
                        "url": job.get("absolute_url", ""),
                        "source": "Greenhouse",
                        "posted_at": job.get("updated_at", ""),
                    }
                )

            return jobs

    except Exception as e:
        logger.warning("Error parsing board %s (%s): %s", board_token, company_name, e)
        return []


async def parse_greenhouse() -> list[dict]:
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CryptoJobsBot/1.0)"
    }

    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = [
            fetch_board_jobs(session, board_token, company_name)
            for board_token, company_name in CRYPTO_GREENHOUSE_BOARDS.items()
        ]
        results = await asyncio.gather(*tasks)

    jobs: list[dict] = []
    for batch in results:
        jobs.extend(batch)

    return jobs

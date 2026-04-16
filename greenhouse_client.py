from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

import aiohttp

from config import GREENHOUSE_BOARDS, HTTP_TIMEOUT_SECONDS, USER_AGENT

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Job:
    title: str
    company: str
    location: str
    url: str
    posted_at: str
    description: str
    source: str = "greenhouse"
    salary: str = "Not specified"
    employment_type: str = "full_time"


API_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def _extract_location(job: dict[str, Any]) -> str:
    location = job.get("location") or {}
    return location.get("name") or "Remote / Not specified"


def _detect_employment_type(title: str, description: str) -> str:
    text = f"{title} {description}".lower()

    if any(x in text for x in ("intern", "internship")):
        return "internship"
    if any(x in text for x in ("contract", "contractor", "freelance")):
        return "freelance"
    if any(x in text for x in ("part-time", "part time")):
        return "part_time"
    return "full_time"


async def fetch_board_jobs(
    session: aiohttp.ClientSession,
    board_token: str,
    company_name: str,
) -> list[Job]:
    url = API_URL.format(board=board_token)

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS)) as resp:
            if resp.status != 200:
                preview = await resp.text()
                logger.warning(
                    "Greenhouse board=%s returned status=%s preview=%s",
                    board_token,
                    resp.status,
                    preview[:200].replace("\n", " "),
                )
                return []

            data = await resp.json(content_type=None)
            jobs: list[Job] = []

            for item in data.get("jobs", []):
                title = (item.get("title") or "").strip()
                description = (item.get("content") or "")[:4000]

                jobs.append(
                    Job(
                        title=title,
                        company=company_name,
                        location=_extract_location(item),
                        url=item.get("absolute_url", ""),
                        posted_at=item.get("updated_at", "") or "",
                        description=description,
                        employment_type=_detect_employment_type(title, description),
                    )
                )

            return jobs

    except Exception as exc:
        logger.warning("Greenhouse fetch failed for %s: %s", board_token, exc)
        return []


async def fetch_jobs_for_boards(board_tokens: list[str]) -> list[Job]:
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {"User-Agent": USER_AGENT}

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        tasks = [
            fetch_board_jobs(session, board_token, GREENHOUSE_BOARDS[board_token])
            for board_token in board_tokens
            if board_token in GREENHOUSE_BOARDS
        ]
        results = await asyncio.gather(*tasks)

    jobs: list[Job] = []
    for chunk in results:
        jobs.extend(chunk)

    return jobs

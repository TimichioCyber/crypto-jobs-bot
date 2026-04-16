import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

ASHBY_ORGS = {
    "fireblocks": "Fireblocks",
    "alchemy": "Alchemy",
    "moonpay": "MoonPay",
    "phantom": "Phantom",
}

API_URL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=apiJobBoardWithTeams"


def detect_format(title: str, employment_type: str = "") -> str:
    text = f"{title} {employment_type}".lower()

    if "intern" in text:
        return "internship"
    if "contract" in text or "freelance" in text:
        return "freelance"
    if "part-time" in text or "part time" in text or "part_time" in text:
        return "part_time"
    return "full_time"


def parse_location(job: dict[str, Any]) -> str:
    location = job.get("location")
    if isinstance(location, str) and location.strip():
        return location.strip()
    return "Remote / Not specified"


async def fetch_org(session: aiohttp.ClientSession, org: str, company_name: str) -> list[dict]:
    payload = {
        "query": """
        query apiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
          jobBoard {
            jobPostingsWithTeams(hostedJobsPageName: $organizationHostedJobsPageName) {
              jobPostings {
                id
                title
                employmentType
                isListed
                publishedAt
                updatedAt
                location
                jobUrl
              }
            }
          }
        }
        """,
        "variables": {
            "organizationHostedJobsPageName": org
        }
    }

    try:
        async with session.post(
            API_URL,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            text_preview = await resp.text()
            logger.info("Ashby %s status=%s", org, resp.status)

            if resp.status != 200:
                logger.warning("Ashby %s bad response: %s", org, text_preview[:200])
                return []

            data = await resp.json(content_type=None)

            postings = (
                data.get("data", {})
                .get("jobBoard", {})
                .get("jobPostingsWithTeams", {})
                .get("jobPostings", [])
            )

            jobs = []
            for job in postings:
                if not job.get("isListed", True):
                    continue

                employment_type = job.get("employmentType") or ""

                jobs.append(
                    {
                        "title": (job.get("title") or "").strip(),
                        "company": company_name,
                        "location": parse_location(job),
                        "salary": "Не указана",
                        "format": detect_format(job.get("title", ""), employment_type),
                        "source": "ashby",
                        "url": job.get("jobUrl", ""),
                        "description": "",
                        "posted_at": job.get("publishedAt") or job.get("updatedAt") or "",
                    }
                )

            return jobs

    except Exception as e:
        logger.warning("Ashby parser failed for %s: %s", org, e)
        return []


async def parse_ashby() -> list[dict]:
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {"User-Agent": "Mozilla/5.0 (CryptoJobsBot/2.0)"}

    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = [
            fetch_org(session, org, company)
            for org, company in ASHBY_ORGS.items()
        ]
        results = await asyncio.gather(*tasks)

    jobs = []
    for part in results:
        jobs.extend(part)

    return jobs

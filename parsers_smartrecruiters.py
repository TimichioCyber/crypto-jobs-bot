import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)

SMARTRECRUITERS_COMPANIES = {
    "CoinMarketCap": "CoinMarketCap",
    "Ledger": "Ledger",
    "Ripple": "Ripple",
}

API_URL = "https://api.smartrecruiters.com/v1/companies/{company}/postings"


def detect_format(job: dict) -> str:
    employment_type = (job.get("typeOfEmployment") or "").lower()
    name = (job.get("name") or "").lower()

    text = f"{employment_type} {name}"

    if "intern" in text:
        return "internship"
    if "contract" in text or "freelance" in text:
        return "freelance"
    if "part-time" in text or "part time" in text:
        return "part_time"
    return "full_time"


def extract_location(job: dict) -> str:
    location = job.get("location") or {}
    city = location.get("city") or ""
    region = location.get("region") or ""
    country = location.get("country") or ""
    remote = location.get("remote") or False

    parts = [x for x in [city, region, country] if x]

    if remote and parts:
        return f"Remote / {', '.join(parts)}"
    if remote:
        return "Remote"
    if parts:
        return ", ".join(parts)
    return "Remote / Not specified"


async def fetch_company(session: aiohttp.ClientSession, company_id: str, company_name: str) -> list[dict]:
    url = API_URL.format(company=company_id)

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            text_preview = await resp.text()
            logger.info("SmartRecruiters %s status=%s", company_id, resp.status)

            if resp.status != 200:
                logger.warning("SmartRecruiters %s bad response: %s", company_id, text_preview[:200])
                return []

            data = await resp.json(content_type=None)
            content = data.get("content", [])
            jobs = []

            for job in content:
                jobs.append(
                    {
                        "title": (job.get("name") or "").strip(),
                        "company": company_name,
                        "location": extract_location(job),
                        "salary": "Не указана",
                        "format": detect_format(job),
                        "source": "smartrecruiters",
                        "url": job.get("ref", "") or job.get("jobAd", {}).get("sections", [{}])[0].get("text", ""),
                        "description": "",
                        "posted_at": job.get("releasedDate") or "",
                    }
                )

            return jobs

    except Exception as e:
        logger.warning("SmartRecruiters parser failed for %s: %s", company_id, e)
        return []


async def parse_smartrecruiters() -> list[dict]:
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {"User-Agent": "Mozilla/5.0 (CryptoJobsBot/2.0)"}

    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = [
            fetch_company(session, company_id, company_name)
            for company_id, company_name in SMARTRECRUITERS_COMPANIES.items()
        ]
        results = await asyncio.gather(*tasks)

    jobs = []
    for part in results:
        jobs.extend(part)

    return jobs

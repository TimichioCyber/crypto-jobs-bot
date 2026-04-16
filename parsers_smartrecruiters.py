"""
SmartRecruiters ATS parser — публичный API.
https://api.smartrecruiters.com/v1/companies/{slug}/postings
"""
import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

COMPANIES = [
    # Известные крипто-компании на SmartRecruiters — если у компании не публичный портал, вернётся 404, просто пропустим
    ("Binance", "Binance"),
    ("OKX", "OKX"),
    ("Bybit", "Bybit"),
]

TIMEOUT = aiohttp.ClientTimeout(total=15)


async def _fetch_company(session: aiohttp.ClientSession, name: str, slug: str) -> list[dict]:
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning(f"SmartRecruiters {name}: HTTP {resp.status}")
                return []
            data = await resp.json()
    except Exception as e:
        logger.warning(f"SmartRecruiters {name}: {e}")
        return []

    jobs = []
    for item in data.get("content", []):
        try:
            title = item.get("name", "")
            loc = item.get("location") or {}
            location = f"{loc.get('city', '')}, {loc.get('country', '')}".strip(", ") or "Remote"
            emp_type = ((item.get("typeOfEmployment") or {}).get("label")) or "Full-time"
            job_url = (item.get("ref") or "").replace("/postings/", f"https://jobs.smartrecruiters.com/{slug}/")
            if not job_url:
                job_url = f"https://jobs.smartrecruiters.com/{slug}/{item.get('id', '')}"
            desc_obj = item.get("jobAd", {}).get("sections", {}) or {}
            desc = ""
            for key in ("companyDescription", "jobDescription", "qualifications"):
                v = (desc_obj.get(key) or {}).get("text", "")
                if v:
                    desc = v
                    break
            desc = desc[:400].replace("\n", " ")

            jobs.append({
                "title": title,
                "company": name,
                "location": location,
                "format": _fmt(emp_type, title, location),
                "salary": "Не указана",
                "description": desc,
                "url": job_url,
                "source": "SmartRecruiters",
                "posted_at": item.get("releasedDate"),
            })
        except Exception as e:
            logger.debug(f"SmartRecruiters parse item fail: {e}")
    return jobs


def _fmt(emp_type: str, title: str, location: str) -> str:
    et = (emp_type or "").lower()
    t = (title + " " + location).lower()
    if "intern" in et or "intern" in t:
        return "Стажировка"
    if "part" in et:
        return "Part-time"
    if "contract" in et or "freelance" in et:
        return "Фриланс"
    if "remote" in t:
        return "Remote / Full-time"
    return "Full-time"


async def parse_smartrecruiters() -> list[dict]:
    all_jobs: list[dict] = []
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        tasks = [_fetch_company(session, name, slug) for name, slug in COMPANIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_jobs.extend(r)
    logger.info(f"SmartRecruiters: total {len(all_jobs)} jobs")
    return all_jobs

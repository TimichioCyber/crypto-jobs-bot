"""
Ashby ATS parser — публичный JSON API: https://api.ashbyhq.com/posting-api/job-board/{slug}
"""
import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

COMPANIES = [
    ("Worldcoin / Tools for Humanity", "toolsforhumanity"),
    ("Risc Zero", "risczero"),
    ("Succinct", "succinctlabs"),
    ("Ethena", "ethena"),
    ("Flashbots", "flashbots"),
    ("Taiko", "taiko"),
]

TIMEOUT = aiohttp.ClientTimeout(total=15)


async def _fetch_company(session: aiohttp.ClientSession, name: str, slug: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning(f"Ashby {name}: HTTP {resp.status}")
                return []
            data = await resp.json()
    except Exception as e:
        logger.warning(f"Ashby {name}: {e}")
        return []

    jobs = []
    for item in data.get("jobs", []):
        try:
            title = item.get("title", "")
            location = item.get("location", "Remote")
            employment_type = item.get("employmentType", "FullTime")
            job_url = item.get("jobUrl", "")
            desc = (item.get("descriptionPlain") or "")[:400].replace("\n", " ")
            salary = _fmt_salary(item.get("compensation"))

            jobs.append({
                "title": title,
                "company": name,
                "location": location,
                "format": _fmt(employment_type, title, location),
                "salary": salary,
                "description": desc,
                "url": job_url,
                "source": "Ashby",
                "posted_at": item.get("publishedAt"),
            })
        except Exception as e:
            logger.debug(f"Ashby parse item fail: {e}")
    return jobs


def _fmt_salary(comp) -> str:
    if not comp:
        return "Не указана"
    try:
        tiers = comp.get("compensationTierSummary") or comp.get("summary")
        if tiers:
            return str(tiers)[:80]
    except Exception:
        pass
    return "Не указана"


def _fmt(employment_type: str, title: str, location: str) -> str:
    et = (employment_type or "").lower()
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


async def parse_ashby() -> list[dict]:
    all_jobs: list[dict] = []
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        tasks = [_fetch_company(session, name, slug) for name, slug in COMPANIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_jobs.extend(r)
    logger.info(f"Ashby: total {len(all_jobs)} jobs")
    return all_jobs

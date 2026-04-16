from __future__ import annotations

from datetime import datetime, timedelta, timezone

from greenhouse_client import Job


ROLE_RULES: dict[str, dict[str, list[str]]] = {
    "developer": {
        "include": [
            "software engineer",
            "backend engineer",
            "frontend engineer",
            "full stack",
            "fullstack",
            "protocol engineer",
            "blockchain engineer",
            "solidity",
            "rust engineer",
            "python engineer",
            "data engineer",
            "platform engineer",
            "infrastructure engineer",
            "devops",
            "site reliability",
            "sre",
            "mobile engineer",
            "security engineer",
            "developer",
        ],
        "exclude": [
            "sales engineer",
            "support engineer",
        ],
    },
    "product": {
        "include": [
            "product manager",
            "product lead",
            "group product manager",
            "senior product manager",
            "principal product manager",
            "product owner",
        ],
        "exclude": [
            "product designer",
            "product marketing",
        ],
    },
    "marketing": {
        "include": [
            "marketing",
            "growth",
            "brand",
            "seo",
            "crm",
            "lifecycle",
            "performance marketing",
            "demand generation",
        ],
        "exclude": [],
    },
    "community": {
        "include": [
            "community",
            "community manager",
            "developer relations",
            "devrel",
            "ecosystem",
            "partnerships",
            "advocate",
            "ambassador",
        ],
        "exclude": [],
    },
    "research": {
        "include": [
            "research analyst",
            "market analyst",
            "investment analyst",
            "crypto analyst",
            "researcher",
            "onchain analyst",
            "fundamental analyst",
            "quant trader",
            "quantitative trader",
            "trader",
            "trading",
            "market maker",
            "execution trader",
        ],
        "exclude": [
            "transaction monitoring",
            "audit",
            "internal audit",
            "compliance",
            "fraud",
            "trust & safety",
            "risk analyst",
            "kyc",
            "aml",
            "operations analyst",
            "business analyst",
            "data analyst",
        ],
    },
    "design": {
        "include": [
            "product designer",
            "ux designer",
            "ui designer",
            "visual designer",
            "brand designer",
            "ux researcher",
            "staff ux researcher",
            "design",
        ],
        "exclude": [],
    },
}


def classify_role(job: Job) -> str | None:
    text = f" {job.title} {job.description} {job.company} ".lower().strip()
    best_role = None
    best_score = 0

    for role, rules in ROLE_RULES.items():
        score = 0

        for term in rules["include"]:
            if term in text:
                score += 3 if " " in term else 1

        for term in rules["exclude"]:
            if term in text:
                score -= 4

        if score > best_score:
            best_score = score
            best_role = role

    return best_role if best_score > 0 else None


def matches_date(job: Job, date_range_days: int) -> bool:
    if not job.posted_at:
        return False

    try:
        dt = datetime.fromisoformat(job.posted_at.replace("Z", "+00:00"))
    except Exception:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(days=date_range_days)
    return dt >= cutoff


def humanize_date(value: str) -> str:
    if not value:
        return "Unknown date"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return value


def filter_jobs(
    jobs: list[Job],
    selected_role: str,
    date_range_days: int,
) -> list[dict]:
    result: list[dict] = []

    for job in jobs:
        detected_role = classify_role(job)
        if detected_role != selected_role:
            continue

        if not matches_date(job, date_range_days):
            continue

        result.append(
            {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "posted_at": job.posted_at,
                "posted_at_human": humanize_date(job.posted_at),
                "description": job.description,
                "employment_type": job.employment_type,
                "salary": job.salary,
                "source": job.source,
                "detected_role": detected_role,
            }
        )

    return dedupe_and_sort(result)


def dedupe_and_sort(jobs: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []

    for job in jobs:
        key = (
            (job.get("url") or "").strip().lower(),
            (job.get("title") or "").strip().lower(),
            (job.get("company") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)

    def parse_dt(value: str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    return sorted(unique, key=lambda x: parse_dt(x.get("posted_at", "")), reverse=True)

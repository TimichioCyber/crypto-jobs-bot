from datetime import datetime, timedelta, timezone
from typing import Iterable


POSITION_KEYWORDS = {
    "developer": [
        "engineer", "developer", "backend", "frontend", "full stack", "fullstack",
        "software", "python", "rust", "solidity", "devops", "sre", "platform",
        "data engineer", "infrastructure",
    ],
    "designer": [
        "designer", "ux", "ui", "product design", "brand designer", "visual designer",
    ],
    "content": [
        "content", "writer", "copywriter", "editor", "research", "analyst",
        "content strategist", "social media",
    ],
    "marketing": [
        "marketing", "growth", "brand", "seo", "crm", "performance marketing",
        "demand generation",
    ],
    "product": [
        "product manager", "product", "pm", "product lead",
    ],
    "hr": [
        "recruiter", "talent", "hr", "human resources", "people ops", "people operations",
    ],
    "community": [
        "community", "community manager", "moderation", "advocacy", "ecosystem",
        "developer relations", "devrel", "partnerships",
    ],
    "trader": [
        "trader", "trading", "quant", "research analyst", "market analyst",
        "portfolio", "investment analyst",
    ],
}


def matches_position(title: str, selected_positions: Iterable[str]) -> bool:
    title_l = (title or "").lower()

    for position in selected_positions:
        keywords = POSITION_KEYWORDS.get(position, [])
        if any(keyword in title_l for keyword in keywords):
            return True

    return False


def matches_format(job_format: str, selected_formats: set[str]) -> bool:
    if not selected_formats:
        return True

    normalized = (job_format or "").lower().replace("-", "_").replace(" ", "_")
    return normalized in selected_formats


def matches_source(source: str, selected_sources: set[str]) -> bool:
    if not selected_sources:
        return True
    return (source or "").lower() in selected_sources


def matches_date(posted_at: str, date_range: str) -> bool:
    if date_range == "all":
        return True

    try:
        days = int(date_range)
    except Exception:
        return True

    if not posted_at:
        return False

    try:
        dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
    except Exception:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return dt >= cutoff


def humanize_posted_at(posted_at: str) -> str:
    if not posted_at:
        return "Дата не указана"

    try:
        dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return posted_at


def apply_filters(jobs: list[dict], prefs: dict) -> list[dict]:
    selected_positions = prefs.get("positions", set())
    selected_formats = prefs.get("formats", set())
    selected_sources = prefs.get("sources", set())
    date_range = prefs.get("date_range", "7")

    result = []

    for job in jobs:
        title = job.get("title", "")
        job_format = job.get("format", "")
        source = job.get("source", "").lower()
        posted_at = job.get("posted_at", "")

        if selected_positions and not matches_position(title, selected_positions):
            continue

        if not matches_format(job_format, selected_formats):
            continue

        if not matches_source(source, selected_sources):
            continue

        if not matches_date(posted_at, date_range):
            continue

        job["posted_at_human"] = humanize_posted_at(posted_at)
        result.append(job)

    return result

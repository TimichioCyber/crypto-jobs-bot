from typing import Iterable


POSITION_KEYWORDS = {
    "developer": [
        "engineer", "developer", "backend", "frontend", "full stack", "fullstack",
        "python", "rust", "solidity", "devops", "sre", "data engineer",
    ],
    "designer": [
        "designer", "product design", "ux", "ui", "brand designer",
    ],
    "content": [
        "content", "writer", "copywriter", "editor", "social", "research analyst",
    ],
    "marketing": [
        "marketing", "growth", "seo", "performance marketing", "brand marketing",
    ],
    "product": [
        "product manager", "product", "pm",
    ],
    "hr": [
        "recruiter", "talent", "human resources", "hr", "people operations",
    ],
    "community": [
        "community", "community manager", "moderation", "advocacy", "ambassador",
    ],
    "trader": [
        "trader", "trading", "quant", "analyst", "portfolio", "market maker",
    ],
}


def matches_position(title: str, selected_positions: Iterable[str]) -> bool:
    title_l = title.lower()

    for position in selected_positions:
        keywords = POSITION_KEYWORDS.get(position, [])
        if any(keyword in title_l for keyword in keywords):
            return True

    return False


def matches_format(job_format: str, selected_formats: set[str]) -> bool:
    if not selected_formats:
        return True

    jf = (job_format or "").lower().replace("-", "_").replace(" ", "_")
    return jf in selected_formats


def apply_filters(jobs: list[dict], prefs: dict) -> list[dict]:
    selected_positions = prefs.get("positions", set())
    selected_formats = prefs.get("formats", set())

    filtered = []

    for job in jobs:
        title = job.get("title", "")
        job_format = job.get("format", "")

        if selected_positions and not matches_position(title, selected_positions):
            continue

        if not matches_format(job_format, selected_formats):
            continue

        filtered.append(job)

    # убираем дубли по url/title/company
    seen = set()
    unique_jobs = []

    for job in filtered:
        key = (
            job.get("url", "").strip().lower(),
            job.get("title", "").strip().lower(),
            job.get("company", "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_jobs.append(job)

    return unique_jobs

from datetime import datetime, timedelta, timezone


ROLE_RULES = {
    "software_engineering": {
        "include": [
            "software engineer", "backend engineer", "frontend engineer", "full stack",
            "fullstack", "developer", "protocol engineer", "blockchain engineer",
            "solidity", "rust engineer", "python engineer", "data engineer",
            "platform engineer", "infrastructure engineer", "devops", "site reliability",
            "sre", "mobile engineer", "security engineer"
        ],
        "exclude": [
            "sales engineer", "support engineer"
        ],
    },
    "research_analyst": {
        "include": [
            "research analyst", "market analyst", "investment analyst",
            "crypto analyst", "researcher", "onchain analyst", "fundamental analyst",
            "market intelligence", "research"
        ],
        "exclude": [
            "transaction monitoring", "audit", "internal audit", "compliance",
            "fraud", "trust & safety", "risk analyst", "kyc", "aml",
            "operations analyst", "business analyst", "data analyst"
        ],
    },
    "trading": {
        "include": [
            "trader", "quant trader", "quantitative trader", "market maker",
            "execution trader", "options trader", "trading"
        ],
        "exclude": [],
    },
    "compliance_risk": {
        "include": [
            "compliance", "aml", "kyc", "risk analyst", "fraud analyst",
            "transaction monitoring", "internal audit", "audit analyst",
            "trust & safety", "investigations", "sanctions", "financial crime",
            "fraud", "risk", "compliance analyst"
        ],
        "exclude": [],
    },
    "data_analyst": {
        "include": [
            "data analyst", "business analyst", "bi analyst", "analytics engineer",
            "business intelligence", "data analytics"
        ],
        "exclude": [
            "research analyst", "investment analyst", "market analyst", "crypto analyst"
        ],
    },
    "product": {
        "include": [
            "product manager", "product lead", "group product manager",
            "senior product manager", "principal product manager", "product owner"
        ],
        "exclude": [
            "product designer", "product marketing"
        ],
    },
    "design": {
        "include": [
            "product designer", "ux designer", "ui designer", "visual designer",
            "brand designer", "ux researcher", "staff ux researcher", "design"
        ],
        "exclude": [],
    },
    "marketing_growth": {
        "include": [
            "marketing", "growth", "brand", "seo", "crm", "lifecycle",
            "performance marketing", "paid media", "demand generation"
        ],
        "exclude": [],
    },
    "content_research": {
        "include": [
            "content", "copywriter", "writer", "editor", "social media",
            "content strategist", "content manager"
        ],
        "exclude": [],
    },
    "community_devrel": {
        "include": [
            "community", "community manager", "developer relations", "devrel",
            "ecosystem", "partnerships", "advocate", "ambassador"
        ],
        "exclude": [],
    },
    "recruiting_hr": {
        "include": [
            "recruiter", "talent", "human resources", "people operations",
            "people partner", "hr", "talent acquisition"
        ],
        "exclude": [],
    },
}


USER_BUCKETS = {
    "developer": {"software_engineering"},
    "designer": {"design"},
    "content": {"content_research"},
    "marketing": {"marketing_growth"},
    "product": {"product"},
    "hr": {"recruiting_hr"},
    "community": {"community_devrel"},
    "trader": {"trading", "research_analyst"},
}


def classify_role(text: str) -> str | None:
    t = f" {(text or '').lower().strip()} "
    best_role = None
    best_score = 0

    for role, rules in ROLE_RULES.items():
        score = 0

        for word in rules["include"]:
            if word in t:
                score += 3 if " " in word else 1

        for word in rules["exclude"]:
            if word in t:
                score -= 4

        if score > best_score:
            best_score = score
            best_role = role

    return best_role if best_score > 0 else None


def matches_position(job: dict, selected_positions) -> bool:
    title = job.get("title", "")
    description = job.get("description", "")
    company = job.get("company", "")
    combined = f"{title} {description} {company}"

    role = classify_role(combined)
    job["detected_role"] = role or "unknown"

    if not role:
        return False

    allowed_roles = set()
    for position in selected_positions:
        allowed_roles.update(USER_BUCKETS.get(position, set()))

    return role in allowed_roles


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
        job_format = job.get("format", "")
        source = job.get("source", "").lower()
        posted_at = job.get("posted_at", "")

        if selected_positions and not matches_position(job, selected_positions):
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

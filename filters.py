"""
Фильтры вакансий по предпочтениям пользователя.
"""
import logging
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

# Ключевые слова для каждой должности (EN + RU)
POSITION_KEYWORDS = {
    "developer": [
        "developer", "engineer", "programmer", "software", "backend", "frontend",
        "fullstack", "full-stack", "smart contract", "solidity", "rust", "golang",
        "python", "typescript", "node", "blockchain", "devops", "sre", "разработ",
        "программист", "инженер",
    ],
    "designer": [
        "designer", "design", "ui", "ux", "product design", "visual", "graphic",
        "motion", "дизайн",
    ],
    "content": [
        "content", "writer", "copywriter", "editor", "journalist", "contributor",
        "контент", "копирайтер", "редактор",
    ],
    "marketing": [
        "marketing", "growth", "seo", "smm", "paid", "performance", "brand",
        "маркет", "маркетолог",
    ],
    "product": [
        "product manager", "product owner", "product lead", "head of product",
        "продакт", "продукт",
    ],
    "hr": [
        "recruiter", "hr ", "people", "talent", "head of people", "рекрут", "эйчар",
    ],
    "community": [
        "community", "moderator", "ambassador", "dao", "discord", "комьюнити", "модератор",
    ],
    "trader": [
        "trader", "trading", "quant", "market maker", "otc", "трейд",
    ],
    "analyst": [
        "analyst", "research", "data scientist", "аналитик", "ресёрч",
    ],
    "bizdev": [
        "business development", "bizdev", "bd ", "sales", "partnerships",
        "account executive", "бизнес", "продаж",
    ],
}


def apply_filters(jobs: list[dict], prefs: dict) -> list[dict]:
    """Главная функция: применяет все фильтры к списку вакансий."""
    if not jobs:
        return []

    out = jobs
    out = _filter_by_position(out, prefs.get("positions") or set())
    out = _filter_by_format(out, prefs.get("formats") or set())
    out = _filter_by_date(out, prefs.get("date_range", "7d"))

    # Сортировка по дате (свежее сверху)
    out.sort(key=_sort_date_key, reverse=True)
    logger.info(f"Filters: {len(jobs)} → {len(out)}")
    return out


def _filter_by_position(jobs: list[dict], positions: set[str]) -> list[dict]:
    if not positions:
        return jobs
    keywords = []
    for p in positions:
        keywords.extend(POSITION_KEYWORDS.get(p, []))
    keywords = [k.lower() for k in keywords]

    out = []
    for j in jobs:
        haystack = (
            (j.get("title", "") or "") + " " +
            (j.get("description", "") or "")
        ).lower()
        if any(k in haystack for k in keywords):
            out.append(j)
    return out


def _filter_by_format(jobs: list[dict], formats: set[str]) -> list[dict]:
    if not formats:
        return jobs
    fmt_map = {
        "full_time": ["full-time", "full time"],
        "part_time": ["part-time", "part time"],
        "freelance": ["фриланс", "contract", "freelance"],
        "internship": ["стажировка", "intern"],
        "remote": ["remote"],
    }
    needles = []
    for f in formats:
        needles.extend(fmt_map.get(f, []))

    out = []
    for j in jobs:
        v = (j.get("format", "") + " " + j.get("location", "")).lower()
        if any(n in v for n in needles):
            out.append(j)
    return out


def _filter_by_date(jobs: list[dict], date_range: str) -> list[dict]:
    if date_range == "all":
        return jobs

    days_map = {"1d": 1, "3d": 3, "7d": 7, "30d": 30}
    days = days_map.get(date_range, 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    out = []
    for j in jobs:
        dt = _parse_job_date(j)
        if dt is None:
            # Нет даты — пропускаем через, предполагаем что свежая
            out.append(j)
        elif dt >= cutoff:
            out.append(j)
    return out


def _parse_job_date(job: dict):
    """Парсит дату из разных полей (ISO / RFC / ms)."""
    # ISO формат
    for key in ("posted_at", "published_at"):
        v = job.get(key)
        if v:
            try:
                return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            except Exception:
                pass

    # RFC 2822 (RSS pubDate)
    v = job.get("posted_at_rfc")
    if v:
        try:
            return parsedate_to_datetime(v)
        except Exception:
            pass

    # ms epoch
    v = job.get("posted_at_ms")
    if v:
        try:
            return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc)
        except Exception:
            pass

    return None


def _sort_date_key(job: dict):
    dt = _parse_job_date(job)
    return dt or datetime.min.replace(tzinfo=timezone.utc)

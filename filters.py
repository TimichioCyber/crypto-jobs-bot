"""
Логика фильтрации вакансий по предпочтениям пользователя
"""

import re
import logging

logger = logging.getLogger(__name__)

# Ключевые слова для определения должности
POSITION_KEYWORDS = {
    'developer': [
        'developer', 'engineer', 'backend', 'frontend', 'fullstack', 'solidity',
        'rust', 'golang', 'python', 'javascript', 'typescript', 'devops', 'blockchain'
    ],
    'designer': [
        'designer', 'ux', 'ui', 'graphic', 'product designer', 'design'
    ],
    'content': [
        'content', 'writer', 'copywriter', 'creator', 'blogger', 'social', 'media'
    ],
    'marketing': [
        'marketing', 'growth', 'campaign', 'digital', 'brand', 'seo', 'sm'
    ],
    'product': [
        'product manager', 'pm', 'product lead', 'product owner'
    ],
    'hr': [
        'hr', 'human resources', 'recruiter', 'recruitment', 'talent'
    ],
    'community': [
        'community', 'moderator', 'ambassador', 'community manager'
    ],
    'trader': [
        'trader', 'trading', 'analyst', 'quantitative', 'quant'
    ],
}

def apply_filters(jobs: list, user_prefs: dict) -> list:
    """
    Фильтрует вакансии по предпочтениям пользователя

    Args:
        jobs: Список вакансий
        user_prefs: Словарь с предпочтениями {positions, formats, min_salary, countries}

    Returns:
        Отфильтрованный список вакансий
    """
    filtered = []

    for job in jobs:
        # Пропускаем если уже были отправлены (можно добавить дедупликацию позже)

        # Фильтр по должности
        if user_prefs.get('positions'):
            if not matches_position(job.get('title', ''), user_prefs['positions']):
                continue

        # Фильтр по формату работы
        if user_prefs.get('formats'):
            if not matches_format(job.get('format', ''), user_prefs['formats']):
                continue

        # Фильтр по зарплате (если указана минимальная)
        if user_prefs.get('min_salary'):
            if not matches_salary(job.get('salary', ''), user_prefs['min_salary']):
                continue

        # Фильтр по странам (если указаны)
        if user_prefs.get('countries'):
            if not matches_location(job.get('location', ''), user_prefs['countries']):
                continue

        filtered.append(job)

    return filtered

def matches_position(title: str, positions: set) -> bool:
    """Проверяет, соответствует ли вакансия выбранным должностям"""
    title_lower = title.lower()

    for position in positions:
        keywords = POSITION_KEYWORDS.get(position, [])
        for keyword in keywords:
            if keyword in title_lower:
                return True

    return False

def matches_format(job_format: str, formats: set) -> bool:
    """Проверяет формат работы"""
    format_lower = job_format.lower()

    for fmt in formats:
        if fmt in format_lower or format_normalize(fmt) in format_lower:
            return True

    return False

def format_normalize(fmt: str) -> str:
    """Нормализирует названия форматов"""
    mapping = {
        'full_time': 'full-time',
        'part_time': 'part-time',
        'freelance': 'freelance',
        'internship': 'intern',
    }
    return mapping.get(fmt, fmt)

def matches_salary(salary_str: str, min_salary: int) -> bool:
    """Проверяет, достаточна ли зарплата"""
    if not salary_str or salary_str == 'Не указана' or salary_str == 'N/A':
        return True  # Если не указана, не фильтруем

    # Ищем числа в строке
    numbers = re.findall(r'\$?([\d,]+)', salary_str)

    if numbers:
        try:
            # Берём первое найденное число
            salary = int(numbers[0].replace(',', ''))
            return salary >= min_salary
        except ValueError:
            return True

    return True

def matches_location(location: str, countries: set) -> bool:
    """Проверяет локацию"""
    if 'remote' in location.lower():
        return True  # Remote подходит для всех

    location_lower = location.lower()
    for country in countries:
        if country.lower() in location_lower:
            return True

    return False

def get_user_preferences(user_id: int) -> dict:
    """Получить предпочтения пользователя (заглушка)"""
    # Позже это будет читать из БД
    return {}

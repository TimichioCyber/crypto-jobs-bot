"""
Парсер для AngelList (криптовалютные стартапы)
"""

import aiohttp
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

async def parse_angellist() -> list:
    """Парсит вакансии с AngelList для крипто-компаний"""
    jobs = []

    try:
        async with aiohttp.ClientSession() as session:
            # AngelList role feed для крипто
            url = "https://angel.co/api/v1/roles/search"
            params = {
                'industry_tags': ['Cryptocurrency'],
                'per_page': 50,
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            async with session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    for role in data.get('roles', []):
                        company = role.get('startup', {})
                        jobs.append({
                            'title': role.get('title', ''),
                            'company': company.get('name', ''),
                            'location': company.get('locations', [{}])[0].get('display_name', 'Remote'),
                            'salary': f"${role.get('salary_min', 0)}-${role.get('salary_max', 0)}" if role.get('salary_min') else 'Не указана',
                            'format': 'Full-time',
                            'description': role.get('description', '')[:300],
                            'url': f"https://angel.co/role/{role.get('id', '')}",
                            'source': 'AngelList',
                            'posted_at': role.get('created_at', ''),
                        })

    except Exception as e:
        logger.error(f"Error parsing AngelList: {e}")

    return jobs

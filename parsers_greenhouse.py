"""
Парсер для Greenhouse (платформа ATS, где публикуют вакансии крипто-компании)
"""

import aiohttp
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

# Крупные крипто-компании, использующие Greenhouse
CRYPTO_COMPANIES = {
    'coinbase': 'Coinbase',
    'kraken': 'Kraken',
    'blockchain': 'Blockchain.com',
    'opensea': 'OpenSea',
    'uniswap': 'Uniswap',
    'aave': 'Aave',
    'curve': 'Curve Finance',
}

async def parse_greenhouse() -> list:
    """Парсит вакансии с Greenhouse для крипто-компаний"""
    jobs = []

    for domain, company_name in CRYPTO_COMPANIES.items():
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://{domain}.greenhouse.io/api/v1/boards/{domain}/jobs"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }

                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()

                        for job in data.get('jobs', [])[:30]:
                            location = ', '.join([l.get('name', '') for l in job.get('offices', [])])
                            jobs.append({
                                'title': job.get('title', ''),
                                'company': company_name,
                                'location': location or 'Remote',
                                'salary': 'Не указана',
                                'format': extract_format(job.get('title', '')),
                                'description': job.get('content', '')[:300],
                                'url': job.get('absolute_url', ''),
                                'source': 'Greenhouse',
                                'posted_at': job.get('published_at', ''),
                            })

        except Exception as e:
            logger.warning(f"Error parsing Greenhouse for {company_name}: {e}")

    return jobs

def extract_format(title: str) -> str:
    """Пытается определить формат работы из названия"""
    title_lower = title.lower()
    if 'intern' in title_lower:
        return 'Стажировка'
    elif 'contractor' in title_lower or 'freelance' in title_lower:
        return 'Фриланс'
    elif 'part' in title_lower:
        return 'Part-time'
    else:
        return 'Full-time'

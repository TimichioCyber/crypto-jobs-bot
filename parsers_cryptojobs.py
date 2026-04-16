"""
Парсер для CryptoJobs.com
"""

import aiohttp
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

async def parse_cryptojobs() -> list:
    """Парсит вакансии с CryptoJobs.com"""
    jobs = []

    try:
        async with aiohttp.ClientSession() as session:
            url = "https://cryptojobs.com/api/jobs"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    for job in data.get('jobs', [])[:50]:  # Берём первые 50
                        jobs.append({
                            'title': job.get('title', ''),
                            'company': job.get('company', ''),
                            'location': job.get('location', ''),
                            'salary': job.get('salary', 'N/A'),
                            'format': job.get('job_type', 'Full-time'),
                            'description': job.get('description', '')[:300],
                            'url': f"https://cryptojobs.com/job/{job.get('id', '')}",
                            'source': 'CryptoJobs.com',
                            'posted_at': job.get('posted_at', ''),
                        })

    except Exception as e:
        logger.error(f"Error parsing CryptoJobs: {e}")

    return jobs

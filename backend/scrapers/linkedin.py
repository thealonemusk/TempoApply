"""
LinkedIn Job Scraper — searches and scrapes jobs from LinkedIn.
Handles public job search and JD extraction using BeautifulSoup to avoid Playwright subprocess issues.
"""
import asyncio
from typing import List, Optional
from loguru import logger
import requests
from bs4 import BeautifulSoup
import urllib.parse

from backend.scrapers.base import normalize_job
from backend.config import settings

def _scrape_job_detail_bs4(url: str) -> dict:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # In public view, jd is in .show-more-less-html__markup
        jd_el = soup.find(class_='show-more-less-html__markup')
        if not jd_el:
            jd_el = soup.find(class_='description__text')
        
        jd_text = jd_el.get_text(separator='\n').strip() if jd_el else ""
        
        return {
            "jd_text": jd_text,
            "easy_apply": False,
            "recruiter_profile": "",
        }
    except Exception as e:
        logger.debug(f"Could not scrape job detail {url}: {e}")
        return {"jd_text": "", "easy_apply": False, "recruiter_name": "", "recruiter_profile": ""}

async def scrape_linkedin_jobs(
    roles: List[str] = None,
    locations: List[str] = None,
    max_jobs: int = 25,
    headless: bool = True,
) -> List[dict]:
    """
    Main LinkedIn scraper entry point using requests/BeautifulSoup.
    Returns list of normalized job dicts.
    """
    roles = roles or settings.target_roles_list
    locations = ["Bengaluru", "Delhi", "Noida", "Pune", "Hyderabad", "Mumbai"]
    all_jobs = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    for role in roles:
        for location in locations:
            try:
                query = urllib.parse.quote(role)
                loc = urllib.parse.quote(location)
                search_url = (
                    f"https://www.linkedin.com/jobs/search/"
                    f"?keywords={query}"
                    f"&location={loc}"
                    f"&f_TPR=r86400"  # Last 24 hours
                    f"&f_E=1%2C2"     # Internship & Entry Level (<2 yrs)
                )
                
                resp = await asyncio.to_thread(requests.get, search_url, headers=headers, timeout=15)
                soup = BeautifulSoup(resp.content, 'html.parser')
                
                job_cards = soup.find_all(class_="base-card")
                if not job_cards:
                    job_cards = soup.find_all(class_="base-search-card")
                
                logger.info(f"Found {len(job_cards)} LinkedIn jobs for '{role}' in '{location}'")
                
                jobs_scraped = 0
                for card in job_cards[:max_jobs]:
                    try:
                        title_el = card.find(class_='base-search-card__title')
                        company_el = card.find(class_='base-search-card__subtitle')
                        link_el = card.find('a', class_='base-card__full-link')
                        
                        title = title_el.text.strip() if title_el else ""
                        company = company_el.text.strip() if company_el else ""
                        url = link_el['href'] if link_el else ""
                        
                        if not title or not url:
                            continue
                            
                        # Normalize URL
                        url = url.split('?')[0]
                        
                        # Get JD
                        detail = await asyncio.to_thread(_scrape_job_detail_bs4, url)
                        
                        raw = {
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": url,
                            **detail,
                        }
                        
                        all_jobs.append(normalize_job(raw, "linkedin"))
                        jobs_scraped += 1
                        
                    except Exception as e:
                        logger.debug(f"LinkedIn bs4: Skipping card due to parse error: {e}")
                        continue
                        
                logger.info(f"Scraped {jobs_scraped} LinkedIn jobs for '{role}'")
                
            except Exception as e:
                logger.error(f"LinkedIn search failed for {role}/{location}: {e}")
                continue
                
    return all_jobs

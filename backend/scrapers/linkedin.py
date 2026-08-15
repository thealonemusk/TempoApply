"""
LinkedIn Job Scraper — searches and scrapes jobs from LinkedIn public listings.
Uses the guest seeMoreJobPostings API with pagination for higher coverage.
"""
import asyncio
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import List, Set

import requests
from bs4 import BeautifulSoup
from loguru import logger

from backend.scrapers.base import normalize_job
from backend.scrapers.filter_utils import is_job_experience_valid
from backend.scrapers.registry import resolve_discovery_roles
from backend.config import settings
from backend.job_freshness import LINKEDIN_TIME_FILTER

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}

# Broader India coverage beyond user settings (scoring still ranks preferred cities).
EXTRA_LOCATIONS = [
    "India",
    "Bengaluru", "Bangalore", "Hyderabad", "Pune", "Mumbai",
    "Gurugram", "Gurgaon", "Noida", "Delhi", "Chennai", "Kolkata",
    "Remote", "Work from Home",
]

LINKEDIN_PAGES = 12
PAGE_SIZE = 10
JD_WORKERS = 12


def _merge_locations(locations: List[str]) -> List[str]:
    merged: List[str] = []
    seen: Set[str] = set()
    for loc in list(locations) + EXTRA_LOCATIONS:
        key = loc.lower().strip()
        if key and key not in seen:
            seen.add(key)
            merged.append(loc.strip())
    return merged


def _search_queries(role: str) -> List[str]:
    """Entry-focused query variants to surface more relevant LinkedIn results."""
    base = role.strip()
    if not base:
        return []
    queries = [base]
    lower = base.lower()
    variants = [
        "entry level",
        "junior",
        "fresher",
        "associate",
        "0-2 years",
        "new grad",
    ]
    for variant in variants:
        if variant not in lower:
            queries.append(f"{base} {variant}")
    return queries[:6]


def _parse_search_cards(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("li")
    results = []

    for card in cards:
        title_el = card.select_one(".base-search-card__title, h3")
        company_el = card.select_one(".base-search-card__subtitle, h4")
        location_el = card.select_one(".job-search-card__location")
        link_el = card.find("a", href=True)

        title = title_el.get_text(strip=True) if title_el else ""
        company = company_el.get_text(strip=True) if company_el else ""
        location = location_el.get_text(strip=True) if location_el else ""
        url = link_el["href"].split("?")[0] if link_el else ""

        if title and url:
            results.append({
                "title": title,
                "company": company,
                "location": location,
                "url": url,
            })

    return results


def _fetch_search_page(keywords: str, location: str, start: int, time_filter: str) -> List[dict]:
    params = urllib.parse.urlencode({
        "keywords": keywords,
        "location": location,
        "f_TPR": time_filter,
        "start": start,
    })
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{params}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    return _parse_search_cards(resp.text)


def _scrape_job_detail_bs4(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.content, "html.parser")

        jd_el = soup.find(class_="show-more-less-html__markup")
        if not jd_el:
            jd_el = soup.find(class_="description__text")

        jd_text = jd_el.get_text(separator="\n").strip() if jd_el else ""
        return {"jd_text": jd_text, "easy_apply": False, "recruiter_profile": ""}
    except Exception as e:
        logger.debug(f"Could not scrape job detail {url}: {e}")
        return {"jd_text": "", "easy_apply": False, "recruiter_name": "", "recruiter_profile": ""}


def _collect_listings(
    roles: List[str],
    locations: List[str],
    max_jobs: int,
) -> List[dict]:
    seen_urls: Set[str] = set()
    listings: List[dict] = []

    for time_filter in [LINKEDIN_TIME_FILTER]:
        for role in roles:
            for query in _search_queries(role):
                for location in locations:
                    for page in range(LINKEDIN_PAGES):
                        start = page * PAGE_SIZE
                        try:
                            batch = _fetch_search_page(query, location, start, time_filter)
                        except Exception as exc:
                            logger.debug(
                                f"LinkedIn page failed for '{query}' / '{location}' @ {start}: {exc}"
                            )
                            break

                        if not batch:
                            break

                        for item in batch:
                            url = item["url"]
                            if url in seen_urls:
                                continue
                            seen_urls.add(url)

                            preview = {
                                "title": item["title"],
                                "company": item["company"],
                                "location": item["location"] or location,
                                "url": url,
                                "jd_text": "",
                            }
                            ok, _ = is_job_experience_valid(preview)
                            if not ok:
                                continue

                            listings.append(preview)
                            if len(listings) >= max_jobs:
                                return listings

                        if len(batch) < PAGE_SIZE:
                            break

        if len(listings) >= max_jobs // 2:
            break

    return listings


def _enrich_listings(listings: List[dict]) -> List[dict]:
    if not listings:
        return []

    with ThreadPoolExecutor(max_workers=JD_WORKERS) as pool:
        details = list(pool.map(_scrape_job_detail_bs4, [j["url"] for j in listings]))

    enriched = []
    for listing, detail in zip(listings, details):
        job_data = {**listing, **detail}
        ok, _ = is_job_experience_valid(job_data)
        if not ok:
            continue
        enriched.append(normalize_job(job_data, "linkedin"))
    return enriched


async def scrape_linkedin_jobs(
    roles: List[str] = None,
    locations: List[str] = None,
    max_jobs: int = 500,
    headless: bool = True,
) -> List[dict]:
    """
    Main LinkedIn scraper entry point.
    Returns list of normalized job dicts.
    """
    roles = resolve_discovery_roles(roles or settings.target_roles_list)
    locations = _merge_locations(locations or settings.preferred_locations_list)

    logger.info(f"LinkedIn: searching {len(roles)} roles across {len(locations)} locations")

    listings = await asyncio.to_thread(_collect_listings, roles, locations, max_jobs)
    logger.info(f"LinkedIn: {len(listings)} listings passed title pre-filter")

    jobs = await asyncio.to_thread(_enrich_listings, listings)
    logger.info(f"LinkedIn: {len(jobs)} jobs after JD validation")
    return jobs

"""
LinkedIn Job Scraper — searches and scrapes jobs from LinkedIn public listings.
Uses the guest seeMoreJobPostings API with pagination for higher coverage.
"""
import asyncio
import re
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import List, Set

import requests
from bs4 import BeautifulSoup
from loguru import logger

from backend.scrapers.base import normalize_job
from backend.scrapers.filter_utils import passes_hard_filters
from backend.scrapers.registry import resolve_discovery_roles
from backend.scan_control import should_stop
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
]
SKIP_SEARCH_LOCATIONS = {"remote", "work from home", "wfh", "anywhere"}

LINKEDIN_PAGES = 3
PAGE_SIZE = 10
JD_WORKERS = 12


def _merge_locations(locations: List[str]) -> List[str]:
    merged: List[str] = []
    seen: Set[str] = set()
    for loc in list(locations) + EXTRA_LOCATIONS:
        key = loc.lower().strip()
        if not key or key in seen or key in SKIP_SEARCH_LOCATIONS:
            continue
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
    if "0-2 years" not in lower:
        queries.append(f"{base} 0-2 years")
    return queries


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


def _linkedin_job_id(url: str) -> str:
    match = re.search(r"(\d{8,})", url or "")
    return match.group(1) if match else ""


def _jd_from_html(html) -> str:
    soup = BeautifulSoup(html, "html.parser")
    jd_el = soup.find(class_="show-more-less-html__markup")
    if not jd_el:
        jd_el = soup.find(class_="description__text")
    return jd_el.get_text(separator="\n").strip() if jd_el else ""


def _scrape_job_detail_bs4(url: str) -> dict:
    empty = {"jd_text": "", "easy_apply": False, "recruiter_profile": ""}
    job_id = _linkedin_job_id(url)
    pages = []
    if job_id:
        pages.append(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}")
    pages.append(url)
    for page_url in pages:
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=15)
            jd_text = _jd_from_html(resp.content)
            if len(jd_text) >= 80:
                return {"jd_text": jd_text, "easy_apply": False, "recruiter_profile": ""}
        except Exception as exc:
            logger.debug(f"Could not scrape job detail {page_url}: {exc}")
    return empty


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
                        if should_stop():
                            return listings
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
                                "platform": "linkedin",
                            }
                            ok, _ = passes_hard_filters(preview, require_jd=False)
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

    reasons: Counter = Counter()
    enriched = []
    for listing, detail in zip(listings, details):
        job_data = {**listing, **detail, "platform": "linkedin"}
        ok, reason = passes_hard_filters(job_data)
        if not ok:
            if "JD missing" in reason:
                reasons["jd_missing"] += 1
            elif "more than" in reason:
                reasons["experience_over_2y"] += 1
            elif "excluded" in reason.lower() or "excluded level" in reason.lower():
                reasons["senior_title"] += 1
            elif "Frontend" in reason:
                reasons["frontend"] += 1
            elif "intern" in reason.lower():
                reasons["intern"] += 1
            else:
                reasons["location_or_other"] += 1
            continue
        enriched.append(normalize_job(job_data, "linkedin"))
    if reasons:
        logger.info(f"LinkedIn: dropped {sum(reasons.values())} after JD — {dict(reasons)}")
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

"""
Company Career Sites Scraper — queries Greenhouse, Lever,
and custom (BeautifulSoup) career pages for top Indian tech companies.

Platform name: "company_careers"
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from loguru import logger
import requests
from bs4 import BeautifulSoup

from backend.scrapers.filter_utils import EXCLUDED_TITLE_KEYWORDS
from backend.scrapers.base import normalize_job
from backend.scrapers.company_list import TOP_COMPANIES

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Career boards update less often than LinkedIn; keep a 7-day window.
FRESHNESS_DAYS = 7

# Extra title aliases beyond the pipeline role strings (SDE, fullstack, etc.)
ROLE_ALIASES = [
    "software engineer",
    "software developer",
    "software development engineer",
    "backend engineer",
    "backend developer",
    "full stack",
    "fullstack",
    "ai engineer",
    "ml engineer",
    "machine learning engineer",
    "python developer",
    "sde",
]


def _is_fresh(timestamp_str: Optional[str] = None, timestamp_ms: Optional[int] = None) -> bool:
    """Check if job is fresh (posted/updated within FRESHNESS_DAYS)."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=FRESHNESS_DAYS)
    
    if timestamp_str:
        try:
            t_str = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(t_str)
            return dt >= cutoff
        except Exception as e:
            logger.debug(f"Error parsing timestamp_str {timestamp_str}: {e}")
            return True
            
    if timestamp_ms:
        try:
            dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            return dt >= cutoff
        except Exception as e:
            logger.debug(f"Error parsing timestamp_ms {timestamp_ms}: {e}")
            return True
            
    return True


def _role_matches(title: str, roles: List[str]) -> bool:
    """Check if a job title matches any of the target roles, excluding senior/lead roles."""
    title_lower = title.lower()

    # Reject if title contains excluded senior/lead/manager keywords
    for keyword in EXCLUDED_TITLE_KEYWORDS:
        if keyword in title_lower:
            return False

    needles = [r.lower() for r in roles] + ROLE_ALIASES
    for role_lower in needles:
        if role_lower in title_lower:
            return True
        role_words = role_lower.split()
        if len(role_words) > 1 and all(w in title_lower for w in role_words):
            return True
    return False


def _location_matches(location_str: str, location_filter: List[str]) -> bool:
    """Check if a location string contains any of the location keywords."""
    if not location_filter:
        return True
    loc_lower = location_str.lower()
    return any(kw in loc_lower for kw in location_filter)


# ─── Greenhouse ─────────────────────────────────────────────────────────────

def _scrape_greenhouse(company: dict, roles: List[str]) -> List[dict]:
    """
    Query Greenhouse public API: https://boards-api.greenhouse.io/v1/boards/{id}/jobs?content=true
    Returns normalized job dicts.
    """
    api_id = company["api_id"]
    name = company["name"]
    loc_filter = company.get("location_filter", [])
    results = []

    url = f"https://boards-api.greenhouse.io/v1/boards/{api_id}/jobs?content=true"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Greenhouse {name}: HTTP {resp.status_code} (bad api_id={api_id}?)")
            return []

        data = resp.json()
        jobs = data.get("jobs", [])
        logger.info(f"Greenhouse {name} ({api_id}): {len(jobs)} total postings")

        for job in jobs:
            title = job.get("title", "")
            if not _role_matches(title, roles):
                continue

            location = job.get("location", {}).get("name", "")
            if not _location_matches(location, loc_filter):
                continue

            updated_at = job.get("updated_at", "")
            if not _is_fresh(timestamp_str=updated_at):
                continue

            job_url = job.get("absolute_url", "")
            # Extract JD from content block
            content = job.get("content", "")
            if content:
                soup = BeautifulSoup(content, "html.parser")
                jd_text = soup.get_text(separator="\n").strip()
            else:
                jd_text = ""

            results.append(normalize_job({
                "title": title,
                "company": name,
                "location": location,
                "url": job_url,
                "jd_text": jd_text,
                "easy_apply": True,
            }, "company_careers"))

    except Exception as e:
        logger.warning(f"Greenhouse {name}: {e}")

    return results


# ─── Lever ──────────────────────────────────────────────────────────────────

def _scrape_lever(company: dict, roles: List[str]) -> List[dict]:
    """
    Query Lever public API: https://api.lever.co/v0/postings/{id}?mode=json
    Returns normalized job dicts.
    """
    api_id = company["api_id"]
    name = company["name"]
    loc_filter = company.get("location_filter", [])
    results = []

    url = f"https://api.lever.co/v0/postings/{api_id}?mode=json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Lever {name}: HTTP {resp.status_code} (bad api_id={api_id}?)")
            return []

        jobs = resp.json()
        if not isinstance(jobs, list):
            logger.debug(f"Lever {name}: unexpected response format")
            return []

        logger.info(f"Lever {name} ({api_id}): {len(jobs)} total postings")

        for job in jobs:
            title = job.get("text", "")
            if not _role_matches(title, roles):
                continue

            # Lever location can be inside categories or top-level
            location = job.get("categories", {}).get("location", "") or job.get("workplaceType", "")
            if not _location_matches(location, loc_filter):
                continue

            # Lever uses epoch milliseconds in `createdAt`
            created_at_ms = job.get("createdAt")
            if created_at_ms and not _is_fresh(timestamp_ms=created_at_ms):
                continue

            job_url = job.get("hostedUrl", "")

            # Build JD from description + lists
            jd_parts = []
            desc_html = job.get("descriptionPlain") or job.get("description", "")
            if desc_html:
                soup = BeautifulSoup(desc_html, "html.parser")
                jd_parts.append(soup.get_text(separator="\n").strip())

            for lst in job.get("lists", []):
                content = lst.get("content", "")
                if content:
                    soup = BeautifulSoup(content, "html.parser")
                    jd_parts.append(soup.get_text(separator="\n").strip())

            jd_text = "\n\n".join(jd_parts)

            results.append(normalize_job({
                "title": title,
                "company": name,
                "location": location,
                "url": job_url,
                "jd_text": jd_text,
                "easy_apply": True,
            }, "company_careers"))

    except Exception as e:
        logger.warning(f"Lever {name}: {e}")

    return results


# ─── Custom HTML Scrape ──────────────────────────────────────────────────────

def _scrape_custom(company: dict, roles: List[str]) -> List[dict]:
    """
    Best-effort BeautifulSoup scraper for companies that host their own careers pages.
    Finds job listing links that match target roles.
    """
    name = company["name"]
    careers_url = company.get("careers_url", "")
    loc_filter = company.get("location_filter", [])
    results = []

    if not careers_url:
        return []

    try:
        resp = requests.get(careers_url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            logger.debug(f"Custom {name}: HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        # Find all anchor tags that look like job listings
        anchors = soup.find_all("a", href=True)

        seen_urls: set = set()
        for a in anchors:
            text = a.get_text(strip=True)
            href = a["href"]

            if not text or not _role_matches(text, roles):
                continue

            # Build absolute URL
            if href.startswith("http"):
                full_url = href
            elif href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(careers_url)
                full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
            else:
                continue

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Best-effort location: look for data attribute or nearby text
            location_text = ""
            parent = a.parent
            if parent:
                location_text = parent.get_text(separator=" ").lower()

            if loc_filter and not _location_matches(location_text, loc_filter):
                continue

            results.append(normalize_job({
                "title": text,
                "company": name,
                "location": "",   # hard to extract consistently
                "url": full_url,
                "jd_text": "",    # would need another request per job
                "easy_apply": False,
            }, "company_careers"))

    except Exception as e:
        logger.warning(f"Custom {name}: {e}")

    return results


# ─── Main Entry Point ────────────────────────────────────────────────────────

async def scrape_company_career_jobs(
    roles: List[str] = None,
    max_jobs: int = 1000,
    companies: List[dict] = None,
) -> List[dict]:
    """
    Scrape company career sites for matching jobs posted in the last FRESHNESS_DAYS days.

    Args:
        roles: List of target role strings (e.g. ['Software Engineer', 'Backend Engineer'])
        max_jobs: Max total jobs to return
        companies: Override company list (defaults to TOP_COMPANIES)

    Returns:
        List of normalized job dicts with platform='company_careers'
    """
    if roles is None:
        from backend.config import settings
        roles = settings.target_roles_list

    company_list = companies or TOP_COMPANIES
    all_jobs: List[dict] = []

    # Dispatch each company scraper in a thread to avoid blocking the event loop
    async def scrape_one(company: dict) -> List[dict]:
        ctype = company.get("type", "skip")
        name = company.get("name", "?")
        if ctype == "skip":
            return []
        try:
            if ctype == "greenhouse":
                return await asyncio.to_thread(_scrape_greenhouse, company, roles)
            elif ctype == "lever":
                return await asyncio.to_thread(_scrape_lever, company, roles)
            elif ctype == "custom":
                return await asyncio.to_thread(_scrape_custom, company, roles)
            else:
                logger.debug(f"Unknown company type '{ctype}' for {name}, skipping.")
                return []
        except Exception as e:
            logger.warning(f"Error scraping {name}: {e}")
            return []

    # Run all companies concurrently (with a semaphore to avoid hammering servers)
    semaphore = asyncio.Semaphore(8)  # max 8 concurrent requests

    async def rate_limited_scrape(company: dict) -> List[dict]:
        async with semaphore:
            result = await scrape_one(company)
            await asyncio.sleep(0.3)   # polite delay
            return result

    tasks = [rate_limited_scrape(c) for c in company_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, list):
            all_jobs.extend(r)
        elif isinstance(r, Exception):
            logger.debug(f"Scrape task raised exception: {r}")

    logger.info(
        f"Company careers: found {len(all_jobs)} matching jobs across "
        f"{len([c for c in company_list if c.get('type') != 'skip'])} companies"
    )

    # Deduplicate by URL, enforce max
    seen: set = set()
    deduped: List[dict] = []
    for job in all_jobs:
        url = job.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduped.append(job)
        if len(deduped) >= max_jobs:
            break

    return deduped

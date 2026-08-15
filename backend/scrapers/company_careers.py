"""
Company Career Sites Scraper — queries Greenhouse, Lever,
and custom (BeautifulSoup) career pages for top Indian tech companies.

Platform name: "company_careers"
"""

import asyncio
import re
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from loguru import logger
import requests
from bs4 import BeautifulSoup

from backend.scrapers.filter_utils import (
    EXCLUDED_TITLE_KEYWORDS,
    INTERN_PATTERN,
    is_job_experience_valid,
    is_career_listing_eligible,
)
from backend.scrapers.base import normalize_job
from backend.scrapers.company_list import TOP_COMPANIES

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

from backend.job_freshness import JOB_FRESHNESS_HOURS

# Extra title aliases beyond the pipeline role strings (SDE, fullstack, etc.)
ROLE_ALIASES = [
    "software engineer",
    "software developer",
    "software development engineer",
    "backend engineer",
    "backend developer",
    "full stack",
    "fullstack",
    "full-stack",
    "ai engineer",
    "ml engineer",
    "machine learning engineer",
    "python developer",
    "java developer",
    "golang developer",
    "go developer",
    "platform engineer",
    "devops engineer",
    "sre",
    "site reliability",
    "sde",
    "new grad",
    "university graduate",
    "graduate engineer",
]


def _is_fresh(timestamp_str: Optional[str] = None, timestamp_ms: Optional[int] = None) -> bool:
    """Check if job is fresh (posted/updated within JOB_FRESHNESS_HOURS)."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=JOB_FRESHNESS_HOURS)

    if timestamp_str:
        try:
            t_str = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(t_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt >= cutoff
        except Exception as e:
            logger.debug(f"Error parsing timestamp_str {timestamp_str}: {e}")
            return False

    if timestamp_ms:
        try:
            dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            return dt >= cutoff
        except Exception as e:
            logger.debug(f"Error parsing timestamp_ms {timestamp_ms}: {e}")
            return False

    return False


def _is_workday_posting_fresh(posted_on: str) -> bool:
    """Parse Workday human-readable postedOn strings."""
    if not posted_on:
        return False

    s = posted_on.lower().strip()
    if "today" in s:
        return True
    if "yesterday" in s:
        return True

    days_match = re.search(r"(\d+)\s*\+?\s*days?", s)
    if days_match:
        return int(days_match.group(1)) * 24 <= JOB_FRESHNESS_HOURS

    weeks_match = re.search(r"(\d+)\s*weeks?", s)
    if weeks_match:
        return int(weeks_match.group(1)) * 7 * 24 <= JOB_FRESHNESS_HOURS

    if "30+" in s or "month" in s or "months" in s:
        return False

    return False


def _passes_career_filters(job_data: dict) -> bool:
    """Apply experience + career-site eligibility checks before returning a job."""
    ok, reason = is_job_experience_valid(job_data)
    if not ok:
        logger.debug(f"Career filter rejected [{job_data.get('company')} - {job_data.get('title')}]: {reason}")
        return False

    ok, reason = is_career_listing_eligible(job_data)
    if not ok:
        logger.debug(f"Career filter rejected [{job_data.get('company')} - {job_data.get('title')}]: {reason}")
        return False

    return True


def _role_matches(title: str, roles: List[str]) -> bool:
    """Check if a job title matches any of the target roles, excluding senior/lead/intern roles."""
    title_lower = title.lower()

    if INTERN_PATTERN.search(title):
        return False

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

        filtered = []
        for job in results:
            if _passes_career_filters(job):
                filtered.append(job)
        results = filtered

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
            if not created_at_ms or not _is_fresh(timestamp_ms=created_at_ms):
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

        filtered = []
        for job in results:
            if _passes_career_filters(job):
                filtered.append(job)
        results = filtered

    except Exception as e:
        logger.warning(f"Lever {name}: {e}")

    return results

WORKDAY_WD_SHARDS = ["wd1", "wd3", "wd5", "wd12", "wd103"]
WORKDAY_PAGE_SIZE = 20  # API returns HTTP 400 above ~20 for most tenants
WORKDAY_MAX_PAGES = 5


def _workday_host_candidates(tenant: str, wd_hint: Optional[str] = None) -> List[str]:
    """Build host list. Never use bare {tenant}.myworkdayjobs.com — it often does not resolve."""
    hosts: List[str] = []
    if wd_hint:
        hosts.append(f"{tenant}.{wd_hint}.myworkdayjobs.com")
    for wd in WORKDAY_WD_SHARDS:
        host = f"{tenant}.{wd}.myworkdayjobs.com"
        if host not in hosts:
            hosts.append(host)
    return hosts


def _resolve_workday_host(
    tenant: str,
    api_id: str,
    hosts: List[str],
    headers: dict,
    search_text: str = "Software Engineer",
) -> Optional[str]:
    payload = {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": search_text}
    for host in hosts:
        url = f"https://{host}/wday/cxs/{tenant}/{api_id}/jobs"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                logger.debug(f"Workday host resolved: {host}")
                return host
        except requests.RequestException as exc:
            logger.debug(f"Workday host probe failed for {host}: {exc}")
    return None


def _fetch_workday_job_detail(
    working_host: str,
    tenant: str,
    api_id: str,
    external_path: str,
) -> str:
    """Fetch full JD text from Workday CXS job detail endpoint."""
    detail_url = f"https://{working_host}/wday/cxs/{tenant}/{api_id}{external_path}"
    try:
        resp = requests.get(detail_url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return ""
        data = resp.json()
        desc_html = data.get("jobPostingInfo", {}).get("jobDescription", "") or ""
        if not desc_html:
            return ""
        return BeautifulSoup(desc_html, "html.parser").get_text(separator="\n").strip()
    except Exception as exc:
        logger.debug(f"Workday detail fetch failed for {external_path}: {exc}")
        return ""


def _scrape_workday(company: dict, roles: List[str]) -> List[dict]:
    """
    Query Workday public JSON API:
    POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{api_id}/jobs
    Returns normalized job dicts.
    """
    tenant = company.get("tenant")
    api_id = company.get("api_id")
    name = company["name"]
    loc_filter = company.get("location_filter", [])
    results = []
    seen_urls: set = set()

    if not tenant or not api_id:
        logger.warning(f"Workday {name}: Missing tenant or api_id")
        return []

    hosts = _workday_host_candidates(tenant, company.get("wd"))
    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    working_host = _resolve_workday_host(tenant, api_id, hosts, headers, roles[0] if roles else "")
    if not working_host:
        logger.warning(f"Workday {name}: Could not resolve host for tenant={tenant} api_id={api_id}")
        return []

    for role in roles:
        try:
            url = f"https://{working_host}/wday/cxs/{tenant}/{api_id}/jobs"
            postings: List[dict] = []
            for page in range(WORKDAY_MAX_PAGES):
                payload = {
                    "appliedFacets": {},
                    "limit": WORKDAY_PAGE_SIZE,
                    "offset": page * WORKDAY_PAGE_SIZE,
                    "searchText": role,
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=15)
                if resp.status_code != 200:
                    if page == 0:
                        logger.warning(f"Workday {name} ({role}): HTTP {resp.status_code}")
                    break
                batch = resp.json().get("jobPostings", [])
                postings.extend(batch)
                if len(batch) < WORKDAY_PAGE_SIZE:
                    break

            logger.info(f"Workday {name} ({role}): {len(postings)} postings found")

            for posting in postings:
                title = posting.get("title", "")
                if not _role_matches(title, [role]):
                    continue

                location = posting.get("locationsText", "")
                if not _location_matches(location, loc_filter):
                    continue

                posted_on = posting.get("postedOn", "")
                if not _is_workday_posting_fresh(posted_on):
                    continue

                external_path = posting.get("externalPath", "")
                if not external_path:
                    continue

                job_url = f"https://{working_host}/{api_id}{external_path}"
                if job_url in seen_urls:
                    continue
                seen_urls.add(job_url)

                jd_text = _fetch_workday_job_detail(working_host, tenant, api_id, external_path)
                job_data = normalize_job({
                    "title": title,
                    "company": name,
                    "location": location,
                    "url": job_url,
                    "jd_text": jd_text,
                    "easy_apply": False,
                }, "company_careers")

                if _passes_career_filters(job_data):
                    results.append(job_data)

        except Exception as e:
            logger.warning(f"Workday {name} ({role}): {e}")

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

        filtered = []
        for job in results:
            if _passes_career_filters(job):
                filtered.append(job)
        results = filtered

    except Exception as e:
        logger.warning(f"Custom {name}: {e}")

    return results


# ─── Main Entry Point ────────────────────────────────────────────────────────

def _expanded_search_roles(roles: List[str]) -> List[str]:
    """Add entry-focused variants for career-site search APIs."""
    expanded: List[str] = []
    seen: set = set()
    extras = [
        "new grad", "university graduate", "entry level", "SDE 1", "associate engineer",
        "junior software engineer", "graduate engineer", "early career", "fresher",
        "software engineer I", "associate software engineer",
    ]
    for role in list(roles) + extras:
        key = role.lower().strip()
        if key and key not in seen:
            seen.add(key)
            expanded.append(role.strip())
    return expanded


async def scrape_company_career_jobs(
    roles: List[str] = None,
    max_jobs: int = 500,
    companies: List[dict] = None,
) -> List[dict]:
    """
    Scrape company career sites for matching jobs posted in the last 72 hours.

    Args:
        roles: List of target role strings (e.g. ['Software Engineer', 'Backend Engineer'])
        max_jobs: Max total jobs to return
        companies: Override company list (defaults to TOP_COMPANIES)

    Returns:
        List of normalized job dicts with platform='company_careers'
    """
    if roles is None:
        from backend.config import settings
        from backend.scrapers.registry import resolve_discovery_roles
        roles = resolve_discovery_roles(settings.target_roles_list)

    search_roles = _expanded_search_roles(roles)
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
                return await asyncio.to_thread(_scrape_greenhouse, company, search_roles)
            elif ctype == "lever":
                return await asyncio.to_thread(_scrape_lever, company, search_roles)
            elif ctype == "workday":
                return await asyncio.to_thread(_scrape_workday, company, search_roles)
            elif ctype == "custom":
                return await asyncio.to_thread(_scrape_custom, company, search_roles)
            else:
                logger.debug(f"Unknown company type '{ctype}' for {name}, skipping.")
                return []
        except Exception as e:
            logger.warning(f"Error scraping {name}: {e}")
            return []

    # Run all companies concurrently (with a semaphore to avoid hammering servers)
    semaphore = asyncio.Semaphore(12)  # max 12 concurrent requests

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

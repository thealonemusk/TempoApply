"""Scraper registry — maps platform keys to scrape callables."""

from typing import Awaitable, Callable, Dict, List

ScrapeFn = Callable[..., Awaitable[List[dict]]]

_FALLBACK_ROLES = [
    "Software Engineer",
    "Backend Engineer",
    "Full Stack Developer",
    "AI Engineer",
    "Software Developer",
    "Platform Engineer",
    "DevOps Engineer",
    "SDE",
    "Machine Learning Engineer",
]

# Extra roles searched during discovery (user target_roles still drive scoring priority).
_DISCOVERY_EXTRA_ROLES = [
    "Associate Software Engineer",
    "Junior Software Engineer",
    "Entry Level Software Engineer",
    "Python Developer",
    "Java Developer",
    "Golang Developer",
    "React Developer",
    "Node.js Developer",
    "Cloud Engineer",
    "Data Engineer",
]


async def _run_linkedin(roles, max_jobs, headless):
    from backend.scrapers.linkedin import scrape_linkedin_jobs
    return await scrape_linkedin_jobs(roles=roles, max_jobs=max_jobs, headless=headless)


async def _run_indeed(roles, max_jobs, headless):
    from backend.scrapers.indeed import scrape_indeed_jobs
    return await scrape_indeed_jobs(roles=roles, max_jobs=max_jobs, headless=headless)


async def _run_naukri(roles, max_jobs, headless):
    from backend.scrapers.naukri import scrape_naukri_jobs
    return await scrape_naukri_jobs(roles=roles, max_jobs=max_jobs, headless=headless)


async def _run_instahyre(roles, max_jobs, headless):
    from backend.scrapers.instahyre import scrape_instahyre_jobs
    return await scrape_instahyre_jobs(roles=roles, max_jobs=max_jobs, headless=headless)


async def _run_wellfound(roles, max_jobs, headless):
    from backend.scrapers.wellfound import scrape_wellfound_jobs
    return await scrape_wellfound_jobs(roles=roles, max_jobs=max_jobs, headless=headless)


async def _run_company_careers(roles, max_jobs, headless):
    from backend.scrapers.company_careers import scrape_company_career_jobs
    return await scrape_company_career_jobs(roles=roles, max_jobs=max_jobs)


SCRAPER_REGISTRY: Dict[str, ScrapeFn] = {
    "linkedin": _run_linkedin,
    "indeed": _run_indeed,
    "naukri": _run_naukri,
    "instahyre": _run_instahyre,
    "wellfound": _run_wellfound,
    "company_careers": _run_company_careers,
}

SCRAPER_LABELS = {
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "naukri": "Naukri",
    "instahyre": "InstaHyre",
    "wellfound": "Wellfound",
    "company_careers": "Company Careers",
    "manual": "Manual",
}


def resolve_roles(settings_roles: List[str]) -> List[str]:
    roles = [r.strip() for r in settings_roles if r.strip()]
    return roles if roles else list(_FALLBACK_ROLES)


def resolve_discovery_roles(settings_roles: List[str]) -> List[str]:
    """Broader role list for scraping; keeps user roles first for priority."""
    merged: List[str] = []
    seen: set = set()
    for role in list(settings_roles) + _FALLBACK_ROLES + _DISCOVERY_EXTRA_ROLES:
        key = role.lower().strip()
        if key and key not in seen:
            seen.add(key)
            merged.append(role.strip())
    return merged if merged else list(_FALLBACK_ROLES)

"""
Naukri.com Job Scraper — searches entry-level (0-2 yr) jobs on Naukri.com.
Uses public search URLs; no login required.
"""
import asyncio
from typing import List, Set

from loguru import logger
from playwright.async_api import async_playwright

from backend.scrapers.base import create_browser_context, normalize_job
from backend.scrapers.filter_utils import passes_hard_filters
from backend.scrapers.registry import resolve_discovery_roles
from backend.config import settings
from backend.job_freshness import NAUKRI_JOB_AGE_DAYS

NAUKRI_LOCATIONS = [
    "Bengaluru", "Hyderabad", "Pune", "Mumbai", "Gurugram", "Gurgaon",
    "Noida", "Delhi", "Chennai", "Kolkata", "Remote",
]
NAUKRI_PAGES = 4


def _merge_locations(locations: List[str]) -> List[str]:
    merged: List[str] = []
    seen: Set[str] = set()
    for loc in list(locations) + NAUKRI_LOCATIONS:
        key = loc.lower().strip()
        if key and key not in seen:
            seen.add(key)
            merged.append(loc.strip())
    return merged


def _role_slug(role: str) -> str:
    return role.lower().replace(" ", "-").replace(".", "")


async def scrape_naukri_jobs(
    roles: List[str] = None,
    locations: List[str] = None,
    max_jobs: int = 300,
    headless: bool = True,
) -> List[dict]:
    """Scrape 0-2 year jobs from Naukri.com."""
    roles = resolve_discovery_roles(roles or settings.target_roles_list)
    locations = _merge_locations(locations or settings.preferred_locations_list)
    all_jobs: List[dict] = []
    seen_urls: Set[str] = set()

    async with async_playwright() as pw:
        browser, ctx = await create_browser_context(pw, headless=headless)
        page = await ctx.new_page()

        for role in roles:
            for location in locations:
                for page_no in range(1, NAUKRI_PAGES + 1):
                    if len(all_jobs) >= max_jobs:
                        break
                    try:
                        job_slug = _role_slug(role)
                        loc_slug = _role_slug(location)
                        search_url = (
                            f"https://www.naukri.com/{job_slug}-jobs-in-{loc_slug}-0-to-2-years"
                            f"?jobAge={NAUKRI_JOB_AGE_DAYS}&sort=1&pageNo={page_no}"
                        )

                        await page.goto(search_url, timeout=30000)
                        await page.wait_for_timeout(2500)

                        job_cards = await page.query_selector_all(
                            ".srp-jobtuple-wrapper, article.jobTuple"
                        )
                        if not job_cards:
                            break

                        logger.info(
                            f"Naukri p{page_no}: {len(job_cards)} cards for '{role}' in '{location}'"
                        )

                        for card in job_cards:
                            if len(all_jobs) >= max_jobs:
                                break
                            try:
                                title_el = await card.query_selector("a.title, .jobTupleHeader a")
                                company_el = await card.query_selector("a.comp-name, .company-name")
                                location_el = await card.query_selector(".loc, .location")
                                exp_el = await card.query_selector(".exp, .experience")

                                title = (await title_el.inner_text()).strip() if title_el else ""
                                company = (await company_el.inner_text()).strip() if company_el else ""
                                location_text = (await location_el.inner_text()).strip() if location_el else ""
                                exp = (await exp_el.inner_text()).strip() if exp_el else ""
                                url = await title_el.get_attribute("href") if title_el else ""

                                if not title or not url or url in seen_urls:
                                    continue

                                preview = {
                                    "title": title,
                                    "company": company,
                                    "location": location_text or location,
                                    "url": url,
                                    "experience_required": exp,
                                    "jd_text": "",
                                    "platform": "naukri",
                                }
                                ok, _ = passes_hard_filters(preview)
                                if not ok:
                                    continue

                                seen_urls.add(url)

                                jd_text = ""
                                try:
                                    detail_page = await ctx.new_page()
                                    await detail_page.goto(url, timeout=25000)
                                    await detail_page.wait_for_timeout(1500)

                                    job_desc_el = await detail_page.query_selector(
                                        ".job-desc, #job-description, .jd-desc"
                                    )
                                    if job_desc_el:
                                        jd_text = (await job_desc_el.inner_text()).strip()

                                    await detail_page.close()
                                except Exception:
                                    pass

                                job_data = {**preview, "jd_text": jd_text}
                                ok, _ = passes_hard_filters(job_data)
                                if not ok:
                                    continue

                                all_jobs.append(normalize_job(job_data, "naukri"))
                                await page.wait_for_timeout(300)
                            except Exception as e:
                                logger.debug(f"Error parsing Naukri card: {e}")
                                continue

                    except Exception as e:
                        logger.error(f"Naukri search failed for {role}/{location} p{page_no}: {e}")
                        break

                if len(all_jobs) >= max_jobs:
                    break
            if len(all_jobs) >= max_jobs:
                break

        await browser.close()

    logger.info(f"Naukri: {len(all_jobs)} jobs after validation")
    return all_jobs

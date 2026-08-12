"""
LinkedIn Job Scraper — searches and scrapes jobs from LinkedIn.
Handles login, job search with filters, Easy Apply detection, and JD extraction.
"""
import asyncio
from typing import List, Optional
from loguru import logger
from playwright.async_api import async_playwright

from backend.scrapers.base import create_browser_context, normalize_job
from backend.config import settings


async def _login(page) -> bool:
    """Log into LinkedIn. Returns True on success."""
    try:
        await page.goto("https://www.linkedin.com/login", timeout=30000)
        await page.wait_for_selector('input[name="session_key"]', timeout=10000)
        await page.fill('input[name="session_key"]', settings.linkedin_email)
        await page.fill('input[name="session_password"]', settings.linkedin_password)
        await page.click('button[type="submit"]')
        await page.wait_for_url("**/feed**", timeout=20000)
        logger.info("✅ LinkedIn login successful")
        return True
    except Exception as e:
        logger.error(f"LinkedIn login failed: {e}")
        return False


async def _scrape_job_detail(page, url: str) -> dict:
    """Scrape a single job detail page."""
    try:
        await page.goto(url, timeout=30000)
        await page.wait_for_selector(".jobs-description", timeout=10000)

        jd_text = await page.inner_text(".jobs-description") or ""
        easy_apply = False
        try:
            btn = await page.query_selector('button.jobs-apply-button')
            if btn:
                btn_text = await btn.inner_text()
                easy_apply = "easy apply" in btn_text.lower()
        except Exception:
            pass

        recruiter_name = ""
        recruiter_profile = ""
        try:
            recruiter_el = await page.query_selector(".hirer-card__hirer-information a")
            if recruiter_el:
                recruiter_name = await recruiter_el.inner_text() or ""
                recruiter_profile = await recruiter_el.get_attribute("href") or ""
        except Exception:
            pass

        return {
            "jd_text": jd_text.strip(),
            "easy_apply": easy_apply,
            "recruiter_name": recruiter_name.strip(),
            "recruiter_profile": recruiter_profile.strip(),
        }
    except Exception as e:
        logger.warning(f"Could not scrape job detail {url}: {e}")
        return {"jd_text": "", "easy_apply": False, "recruiter_name": "", "recruiter_profile": ""}


async def scrape_linkedin_jobs(
    roles: List[str] = None,
    locations: List[str] = None,
    max_jobs: int = 30,
    headless: bool = True,
) -> List[dict]:
    """
    Main LinkedIn scraper entry point.
    Returns list of normalized job dicts.
    """
    roles = roles or settings.target_roles_list
    locations = locations or settings.preferred_locations_list
    all_jobs = []

    async with async_playwright() as pw:
        browser, ctx = await create_browser_context(pw, headless=headless)
        page = await ctx.new_page()

        if not await _login(page):
            await browser.close()
            return []

        for role in roles[:2]:  # Limit to first 2 roles per scan
            for location in locations[:2]:
                try:
                    search_url = (
                        f"https://www.linkedin.com/jobs/search/"
                        f"?keywords={role.replace(' ', '%20')}"
                        f"&location={location.replace(' ', '%20')}"
                        f"&f_TPR=r86400"  # Last 24 hours
                        f"&sortBy=DD"
                    )
                    await page.goto(search_url, timeout=30000)
                    await page.wait_for_selector(".jobs-search__results-list", timeout=15000)
                    await page.wait_for_timeout(2000)

                    # Scroll to load more jobs
                    for _ in range(3):
                        await page.keyboard.press("End")
                        await page.wait_for_timeout(1500)

                    job_cards = await page.query_selector_all(".jobs-search__results-list > li")
                    logger.info(f"Found {len(job_cards)} LinkedIn jobs for '{role}' in '{location}'")

                    jobs_scraped = 0
                    for card in job_cards[:max_jobs]:
                        try:
                            title_el = await card.query_selector(".job-card-list__title")
                            company_el = await card.query_selector(".job-card-container__primary-description")
                            location_el = await card.query_selector(".job-card-container__metadata-item")
                            link_el = await card.query_selector("a.job-card-list__title")

                            title = (await title_el.inner_text()).strip() if title_el else ""
                            company = (await company_el.inner_text()).strip() if company_el else ""
                            location_text = (await location_el.inner_text()).strip() if location_el else ""
                            url = await link_el.get_attribute("href") if link_el else ""

                            if not title or not url:
                                continue

                            # Full URL
                            if url.startswith("/"):
                                url = f"https://www.linkedin.com{url.split('?')[0]}"

                            # Get job details
                            detail = await _scrape_job_detail(page, url)

                            raw = {
                                "title": title,
                                "company": company,
                                "location": location_text,
                                "url": url,
                                **detail,
                            }
                            all_jobs.append(normalize_job(raw, "linkedin"))
                            jobs_scraped += 1
                            await page.wait_for_timeout(1000)
                        except Exception as e:
                            logger.warning(f"Error parsing LinkedIn job card: {e}")
                            continue

                    logger.info(f"Scraped {jobs_scraped} LinkedIn jobs for '{role}' in '{location}'")
                    await page.wait_for_timeout(3000)

                except Exception as e:
                    logger.error(f"LinkedIn search failed for {role}/{location}: {e}")
                    continue

        await browser.close()

    return all_jobs

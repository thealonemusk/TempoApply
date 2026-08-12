"""
Indeed Job Scraper — searches and scrapes jobs from Indeed India.
"""
import asyncio
from typing import List
from loguru import logger
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

from backend.scrapers.base import create_browser_context, normalize_job
from backend.config import settings


async def scrape_indeed_jobs(
    roles: List[str] = None,
    locations: List[str] = None,
    max_jobs: int = 25,
    headless: bool = True,
) -> List[dict]:
    """Scrape jobs from Indeed India."""
    roles = roles or settings.target_roles_list
    locations = locations or settings.preferred_locations_list
    all_jobs = []

    async with async_playwright() as pw:
        browser, ctx = await create_browser_context(pw, headless=headless)
        page = await ctx.new_page()

        for role in roles[:2]:
            for location in locations[:2]:
                try:
                    search_url = (
                        f"https://in.indeed.com/jobs"
                        f"?q={role.replace(' ', '+')}"
                        f"&l={location.replace(' ', '+')}"
                        f"&sort=date&fromage=1"  # Last 1 day
                    )
                    await page.goto(search_url, timeout=30000)
                    await page.wait_for_timeout(3000)

                    # Handle any modals
                    try:
                        close_btn = await page.query_selector('[aria-label="close"]')
                        if close_btn:
                            await close_btn.click()
                    except Exception:
                        pass

                    job_cards = await page.query_selector_all('[data-testid="slider_item"]')
                    if not job_cards:
                        job_cards = await page.query_selector_all(".job_seen_beacon")

                    logger.info(f"Found {len(job_cards)} Indeed jobs for '{role}' in '{location}'")

                    for card in job_cards[:max_jobs]:
                        try:
                            title_el = await card.query_selector('[data-testid="jobTitle"] span, h2.jobTitle span')
                            company_el = await card.query_selector('[data-testid="company-name"], .companyName')
                            location_el = await card.query_selector('[data-testid="text-location"], .companyLocation')
                            link_el = await card.query_selector('a[data-testid="job-title-link"], a.jcs-JobTitle')

                            title = (await title_el.inner_text()).strip() if title_el else ""
                            company = (await company_el.inner_text()).strip() if company_el else ""
                            location_text = (await location_el.inner_text()).strip() if location_el else ""
                            href = await link_el.get_attribute("href") if link_el else ""

                            if not title or not href:
                                continue

                            url = f"https://in.indeed.com{href}" if href.startswith("/") else href

                            # Click to get JD in side panel
                            jd_text = ""
                            try:
                                if link_el:
                                    await link_el.click()
                                    await page.wait_for_timeout(2000)
                                    jd_el = await page.query_selector(
                                        "[id='jobDescriptionText'], .jobDescriptionContent"
                                    )
                                    if jd_el:
                                        jd_text = await jd_el.inner_text()
                            except Exception:
                                pass

                            raw = {
                                "title": title,
                                "company": company,
                                "location": location_text,
                                "url": url,
                                "jd_text": jd_text.strip(),
                                "easy_apply": False,
                            }
                            all_jobs.append(normalize_job(raw, "indeed"))
                            await page.wait_for_timeout(800)
                        except Exception as e:
                            logger.warning(f"Error parsing Indeed card: {e}")
                            continue

                    logger.info(f"Scraped {len(all_jobs)} Indeed jobs so far")
                    await page.wait_for_timeout(2000)

                except Exception as e:
                    logger.error(f"Indeed search failed for {role}/{location}: {e}")
                    continue

        await browser.close()

    return all_jobs

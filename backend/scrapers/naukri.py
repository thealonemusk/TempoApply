"""
Naukri.com Job Scraper — searches jobs on Naukri.com.
Handles login and job card parsing with recruiter info extraction.
"""
import asyncio
from typing import List
from loguru import logger
from playwright.async_api import async_playwright

from backend.scrapers.base import create_browser_context, normalize_job
from backend.config import settings


async def _login_naukri(page) -> bool:
    try:
        await page.goto("https://www.naukri.com/", timeout=30000)
        await page.wait_for_timeout(2000)

        # Click login button
        try:
            login_btn = await page.query_selector('[title="Jobseeker Login"]')
            if login_btn:
                await login_btn.click()
                await page.wait_for_timeout(1500)
        except Exception:
            await page.goto("https://www.naukri.com/nlogin/login", timeout=30000)

        await page.fill('input[placeholder="Enter your active Email ID / Username"]', settings.naukri_email)
        await page.fill('input[placeholder="Enter your password"]', settings.naukri_password)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(4000)
        logger.info("✅ Naukri login successful")
        return True
    except Exception as e:
        logger.error(f"Naukri login failed: {e}")
        return False


async def scrape_naukri_jobs(
    roles: List[str] = None,
    locations: List[str] = None,
    max_jobs: int = 25,
    headless: bool = True,
) -> List[dict]:
    """Scrape jobs from Naukri.com."""
    roles = roles or settings.target_roles_list
    locations = locations or settings.preferred_locations_list
    all_jobs = []

    async with async_playwright() as pw:
        browser, ctx = await create_browser_context(pw, headless=headless)
        page = await ctx.new_page()

        if not await _login_naukri(page):
            await browser.close()
            return []

        for role in roles[:2]:
            for location in locations[:2]:
                try:
                    search_url = (
                        f"https://www.naukri.com/{role.lower().replace(' ', '-')}"
                        f"-jobs-in-{location.lower().replace(' ', '-')}"
                        f"?jobAge=1&sort=1"  # Last 1 day, newest first
                    )
                    await page.goto(search_url, timeout=30000)
                    await page.wait_for_timeout(3000)

                    job_cards = await page.query_selector_all(".srp-jobtuple-wrapper, article.jobTuple")
                    logger.info(f"Found {len(job_cards)} Naukri jobs for '{role}' in '{location}'")

                    for card in job_cards[:max_jobs]:
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

                            if not title or not url:
                                continue

                            # Get JD from detail page
                            jd_text = ""
                            recruiter_name = ""
                            try:
                                detail_page = await ctx.new_page()
                                await detail_page.goto(url, timeout=25000)
                                await detail_page.wait_for_timeout(2000)

                                job_desc_el = await detail_page.query_selector(
                                    ".job-desc, #job-description, .jd-desc"
                                )
                                if job_desc_el:
                                    jd_text = await job_desc_el.inner_text()

                                recruiter_el = await detail_page.query_selector(".recruiter-name, .contact-name")
                                if recruiter_el:
                                    recruiter_name = await recruiter_el.inner_text()

                                await detail_page.close()
                            except Exception:
                                pass

                            raw = {
                                "title": title,
                                "company": company,
                                "location": location_text,
                                "url": url,
                                "experience_required": exp,
                                "jd_text": jd_text.strip(),
                                "recruiter_name": recruiter_name.strip(),
                            }
                            all_jobs.append(normalize_job(raw, "naukri"))
                            await page.wait_for_timeout(600)
                        except Exception as e:
                            logger.warning(f"Error parsing Naukri card: {e}")
                            continue

                except Exception as e:
                    logger.error(f"Naukri search failed for {role}/{location}: {e}")
                    continue

        await browser.close()

    return all_jobs

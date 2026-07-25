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
    """Login to Naukri using Google OAuth (no password required)."""
    try:
        await page.goto("https://www.naukri.com/nlogin/login", timeout=30000)
        await page.wait_for_timeout(2000)

        # Click the "Login with Google" button
        google_btn = await page.query_selector(
            'a[href*="google"], button:has-text("Google"), [class*="google"], [data-ga*="google"]'
        )
        if not google_btn:
            # Try alternate selector for Naukri's Google login link
            google_btn = await page.query_selector('a.google-login, a[title*="Google"], .googleBtn')

        if not google_btn:
            logger.error("Naukri: Could not find 'Login with Google' button")
            return False

        # Google OAuth opens in a popup — wait for it
        async with page.context.expect_page() as popup_info:
            await google_btn.click()
        google_page = await popup_info.value
        await google_page.wait_for_load_state("domcontentloaded", timeout=20000)
        await google_page.wait_for_timeout(2000)

        # Fill Google email
        email_input = await google_page.query_selector('input[type="email"]')
        if email_input:
            await email_input.fill(settings.naukri_email)
            await google_page.click('button:has-text("Next"), #identifierNext')
            await google_page.wait_for_timeout(3000)

        # If account-picker appears, click the matching account
        try:
            account = await google_page.query_selector(f'[data-email="{settings.naukri_email}"]')
            if account:
                await account.click()
                await google_page.wait_for_timeout(3000)
        except Exception:
            pass

        # Wait for redirect back to Naukri
        await page.wait_for_timeout(6000)
        logger.info("✅ Naukri Google login successful")
        return True
    except Exception as e:
        logger.error(f"Naukri Google login failed: {e}")
        return False


async def scrape_naukri_jobs(
    roles: List[str] = None,
    locations: List[str] = None,
    max_jobs: int = 25,
    headless: bool = True,
) -> List[dict]:
    """Scrape jobs from Naukri.com without login requirement."""
    roles = roles or settings.target_roles_list
    locations = ["Bengaluru", "Delhi", "Noida", "Pune", "Hyderabad", "Mumbai" , "Gurugram"]
    all_jobs = []

    async with async_playwright() as pw:
        # Launch browser without login dependencies 
        browser, ctx = await create_browser_context(pw, headless=headless)
        page = await ctx.new_page()

        # REMOVED: Google login requirement. Public search works best for simply harvesting URLs.
        
        for role in roles:
            for location in locations:
                try:
                    job_slug = role.lower().replace(' ', '-')
                    loc_slug = location.lower().replace(' ', '-')
                    # Appending 0-to-2-years to the slug filter to restrict experience
                    search_url = f"https://www.naukri.com/{job_slug}-jobs-in-{loc_slug}-0-to-2-years?jobAge=1&sort=1"
                    
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

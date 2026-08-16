"""
Base scraper utilities — shared helpers for all platform scrapers.
"""
import hashlib
from typing import Optional
from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


def url_hash(url: str) -> str:
    """Stable hash for deduplication."""
    return hashlib.md5(url.encode()).hexdigest()


async def create_browser_context(playwright, headless: bool = True) -> tuple:
    """Launch a Chromium browser with realistic settings."""
    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-IN",
    )
    # Hide webdriver flag
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)
    return browser, context


def normalize_job(raw: dict, platform: str) -> dict:
    """Normalize a raw scraped job dict to standard schema."""
    from backend.applier.ats import detect_ats

    url = raw.get("url", "").strip()
    return {
        "title": raw.get("title", "").strip(),
        "company": raw.get("company", "").strip(),
        "platform": platform,
        "url": url,
        "location": raw.get("location", "").strip(),
        "experience_required": raw.get("experience_required", "").strip(),
        "salary_range": raw.get("salary_range", "").strip(),
        "jd_text": raw.get("jd_text", "").strip(),
        "easy_apply": raw.get("easy_apply", False),
        "recruiter_name": raw.get("recruiter_name", "").strip(),
        "recruiter_profile": raw.get("recruiter_profile", "").strip(),
        "ats_type": raw.get("ats_type") or detect_ats(url),
        "relevance_score": 0.0,
        "fit_reason": "",
        "missing_skills": "[]",
        "seniority_level": "",
        "is_engineering_role": True,
        "status": "discovered",
    }

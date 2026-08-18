"""Open a LinkedIn job, log in if needed, then follow the company ATS apply URL."""
from __future__ import annotations

from typing import Optional
from urllib.parse import unquote, urlparse

from loguru import logger
from playwright.async_api import Page

from backend.applier.ats import detect_ats, first_ats_url
from backend.applier.control import should_stop
from backend.applier.filler import click_named_button, dismiss_overlays, wait_settled

HREF_JS = """() => {
  const out = [];
  for (const a of document.querySelectorAll('a[href]')) out.push(a.href);
  return out;
}"""

LOGIN_WAIT_SEC = 300
AUTH_MARKERS = (
    "/login",
    "uas/login",
    "/signup",
    "cold-join",
    "checkpoint",
    "challenge",
    "authwall",
)


def _on_auth_wall(url: str) -> bool:
    u = (url or "").lower()
    return any(marker in u for marker in AUTH_MARKERS)


async def _linkedin_logged_in(page: Page) -> bool:
    url = page.url or ""
    if _on_auth_wall(url):
        return False
    return "linkedin.com" in url.lower()


async def wait_for_linkedin_login(page: Page, seconds: int = LOGIN_WAIT_SEC) -> bool:
    """Leave this window open so the user can finish LinkedIn or Google sign-in."""
    if await _linkedin_logged_in(page):
        return True
    logger.warning(
        "Sign into LinkedIn in this Chrome window (Google sign-in is fine). "
        f"Waiting up to {seconds // 60} minutes..."
    )
    for _ in range(seconds):
        if should_stop():
            logger.warning("LinkedIn login wait stopped")
            return False
        await page.wait_for_timeout(1000)
        if await _linkedin_logged_in(page):
            logger.info("LinkedIn signed in")
            return True
    logger.warning(f"LinkedIn session not established url={page.url}")
    return False


async def ensure_linkedin_session(page: Page) -> bool:
    """Reuse the persistent Chrome profile; wait if this window still needs a sign-in."""
    try:
        await page.goto("https://www.linkedin.com/feed", wait_until="domcontentloaded", timeout=45000)
        await wait_settled(page, 1500)
        await dismiss_overlays(page)
    except Exception as exc:
        logger.warning(f"LinkedIn login page failed: {exc}")
        return False
    if await _linkedin_logged_in(page):
        logger.info("LinkedIn session already active")
        return True
    return await wait_for_linkedin_login(page)


async def linkedin_login_if_needed(page: Page) -> bool:
    await dismiss_overlays(page)
    if await _linkedin_logged_in(page):
        return True
    return await wait_for_linkedin_login(page)


async def _extract_offsite_url(page: Page, jd_text: str = "") -> str:
    hrefs = []
    try:
        hrefs = await page.evaluate(HREF_JS)
    except Exception:
        hrefs = []
    html = ""
    try:
        html = await page.content()
    except Exception:
        pass
    found = first_ats_url(jd_text, " ".join(hrefs), html)
    if found:
        return found
    for href in hrefs:
        if "externalApply" in href or "applyUrl" in href:
            parsed = urlparse(href)
            qs = unquote(parsed.query)
            nested = first_ats_url(qs, href)
            if nested:
                return nested
    return ""


async def _click_offsite_apply(page: Page) -> Optional[Page]:
    context = page.context
    selectors = (
        "a.jobs-apply-button",
        "button.jobs-apply-button",
        'a[data-tracking-control-name*="apply"]',
        'button[data-tracking-control-name*="apply"]',
        'a:has-text("Apply on company website")',
        'a:has-text("Apply on company")',
        'button:has-text("Apply on company website")',
    )
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if not await loc.count() or not await loc.first.is_visible():
                continue
            text = ((await loc.first.inner_text()) or "").lower()
            if "easy apply" in text:
                continue
            try:
                async with context.expect_page(timeout=6000) as new_info:
                    await loc.first.click(timeout=4000)
                new_page = await new_info.value
                await new_page.wait_for_load_state("domcontentloaded", timeout=30000)
                return new_page
            except Exception:
                await loc.first.click(timeout=4000)
                await wait_settled(page, 1500)
                return page
        except Exception:
            continue
    await click_named_button(
        page,
        ("Apply on company website", "Continue to apply"),
        timeout=3000,
    )
    await wait_settled(page, 1200)
    return page


async def open_from_linkedin(page: Page, jd_text: str = "") -> Page:
    """If this is a LinkedIn posting, log in and jump to the company ATS page when possible."""
    if "linkedin.com" not in (page.url or "").lower():
        return page
    await dismiss_overlays(page)

    url = (page.url or "").lower()
    if "signup" in url or "cold-join" in url:
        parsed = urlparse(page.url)
        qs = unquote(parsed.query)
        redirect = ""
        for part in qs.split("&"):
            if part.startswith("session_redirect="):
                redirect = unquote(part.split("=", 1)[1])
                break
        sign_in = page.get_by_role("link", name="Sign in", exact=False)
        try:
            if await sign_in.count() and await sign_in.first.is_visible():
                await sign_in.first.click()
                await wait_settled(page, 1500)
        except Exception:
            pass
        await linkedin_login_if_needed(page)
        if redirect and "linkedin.com" in redirect:
            try:
                await page.goto(redirect, wait_until="domcontentloaded", timeout=45000)
                await wait_settled(page)
            except Exception:
                pass

    await linkedin_login_if_needed(page)
    await dismiss_overlays(page)

    offsite = await _extract_offsite_url(page, jd_text)
    if offsite and detect_ats(offsite) != "unknown":
        logger.info(f"LinkedIn offsite apply URL: {offsite}")
        await page.goto(offsite, wait_until="domcontentloaded", timeout=45000)
        await wait_settled(page)
        return page

    next_page = await _click_offsite_apply(page)
    await dismiss_overlays(next_page)
    if detect_ats(next_page.url) != "unknown":
        return next_page
    offsite = await _extract_offsite_url(next_page, jd_text)
    if offsite and detect_ats(offsite) != "unknown":
        await next_page.goto(offsite, wait_until="domcontentloaded", timeout=45000)
        await wait_settled(next_page)
    return next_page


async def _is_easy_apply(page: Page) -> bool:
    loc = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')")
    try:
        if not await loc.count() or not await loc.first.is_visible():
            return False
        text = ((await loc.first.inner_text()) or "").lower()
        label = (await loc.first.get_attribute("aria-label") or "").lower()
        return "easy apply" in text or "easy apply" in label
    except Exception:
        return False


async def apply_linkedin_easy(
    page: Page,
    profile,
    resume,
    job_title: str,
    company: str,
    auto_submit: bool,
    job_id: str,
) -> dict:
    from backend.applier.filler import (
        fill_form,
        finish_application,
        screenshot_failure,
        unfilled_required,
        upload_resume,
        wait_settled,
    )
    from pathlib import Path

    log_dir = Path(__file__).resolve().parent.parent.parent / "data" / "apply_logs"
    btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
    try:
        await btn.click(timeout=4000)
    except Exception:
        await screenshot_failure(page, log_dir / f"{job_id}.png")
        return {
            "status": "needs_review",
            "message": "LinkedIn Easy Apply button was not clickable.",
            "ats": "linkedin",
        }
    await wait_settled(page, 1200)
    info = {"filled": 0, "unknown_required": [], "resume_uploaded": False}
    if await upload_resume(page, resume, page=page):
        info["resume_uploaded"] = True
    extra = await fill_form(page, profile, job_title, company)
    info["filled"] += extra.get("filled", 0)
    info["unknown_required"] = extra.get("unknown_required") or []

    for _ in range(8):
        leftover = await unfilled_required(page)
        submit = page.get_by_role("button", name="Submit application", exact=False)
        review = page.get_by_role("button", name="Review", exact=False)
        nxt = page.get_by_role("button", name="Next", exact=False)
        cont = page.get_by_role("button", name="Continue", exact=False)
        try:
            if await submit.count() and await submit.first.is_visible() and not leftover:
                return await finish_application(
                    page, page, profile, auto_submit, job_id, info, log_dir
                )
        except Exception:
            pass
        moved = False
        for loc in (nxt, cont, review):
            try:
                if await loc.count() and await loc.first.is_visible():
                    await loc.first.click(timeout=3000)
                    moved = True
                    break
            except Exception:
                continue
        if not moved:
            break
        await wait_settled(page, 900)
        extra = await fill_form(page, profile, job_title, company)
        info["filled"] += extra.get("filled", 0)
        if await upload_resume(page, resume, page=page):
            info["resume_uploaded"] = True
    return await finish_application(page, page, profile, auto_submit, job_id, info, log_dir)

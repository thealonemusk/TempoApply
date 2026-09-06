"""Open a LinkedIn job, log in if needed, then follow the company ATS apply URL."""
from __future__ import annotations

import asyncio
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
    signed_in, _ = await linkedin_session_state(page)
    return signed_in


async def linkedin_session_state(
    page: Page, wait_seconds: int = LOGIN_WAIT_SEC
) -> tuple[bool, str]:
    """
    Preflight check for the persistent profile's LinkedIn session.

    Returns (signed_in, human-readable detail). Callers use the detail to tell
    the user *why* a run could not start instead of silently blocking on a
    login prompt for minutes.
    """
    try:
        await page.goto(
            "https://www.linkedin.com/feed", wait_until="domcontentloaded", timeout=45000
        )
        await wait_settled(page, 1500)
        await dismiss_overlays(page)
    except Exception as exc:
        logger.warning(f"LinkedIn feed did not load: {exc}")
        return False, "LinkedIn did not load"

    if await _linkedin_logged_in(page):
        logger.info("LinkedIn session already active")
        return True, "session active"

    if wait_seconds <= 0:
        return False, "not signed in"

    signed_in = await wait_for_linkedin_login(page, seconds=wait_seconds)
    if signed_in:
        return True, "signed in during preflight"
    if should_stop():
        return False, "stopped by user"
    return False, f"no sign-in within {wait_seconds}s"


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


async def page_opened_since(context, existing_pages, timeout_ms: int = 15000) -> Optional[Page]:
    """Return a tab that appeared after a click (company site / ATS)."""
    existing = {id(p) for p in existing_pages}
    waited = 0
    while waited < timeout_ms:
        for p in context.pages:
            if id(p) in existing or p.is_closed():
                continue
            try:
                await p.wait_for_load_state("domcontentloaded", timeout=25000)
            except Exception:
                pass
            try:
                await p.bring_to_front()
            except Exception:
                pass
            await wait_settled(p, 800)
            return p
        await asyncio.sleep(0.25)
        waited += 250
    return None


async def offsite_page(page: Page) -> Page:
    """Use the company/ATS tab if LinkedIn left one open."""
    best = None
    for p in page.context.pages:
        if p.is_closed():
            continue
        u = (p.url or "").lower()
        if not u.startswith("http") or "linkedin.com" in u:
            continue
        if detect_ats(p.url) != "unknown":
            best = p
            break
        best = p
    if best is None:
        return page
    try:
        await best.bring_to_front()
    except Exception:
        pass
    return best


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
        'button:has-text("Apply on company")',
        'a:has-text("Apply")',
        'button:has-text("Apply")',
    )
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if not await loc.count() or not await loc.first.is_visible():
                continue
            text = ((await loc.first.inner_text()) or "").lower()
            label = (await loc.first.get_attribute("aria-label") or "").lower()
            if "easy apply" in text or "easy apply" in label:
                continue
            existing = list(context.pages)
            await loc.first.click(timeout=4000)
            opened = await page_opened_since(context, existing)
            if opened:
                logger.info(f"LinkedIn opened company tab: {opened.url}")
                return opened
            await wait_settled(page, 1500)
            if "linkedin.com" not in (page.url or "").lower():
                return page
            adopted = await offsite_page(page)
            if adopted != page:
                logger.info(f"LinkedIn company tab already open: {adopted.url}")
                return adopted
            return page
        except Exception:
            continue
    existing = list(context.pages)
    await click_named_button(
        page,
        ("Apply on company website", "Continue to apply"),
        timeout=3000,
    )
    opened = await page_opened_since(context, existing, timeout_ms=8000)
    if opened:
        return opened
    await wait_settled(page, 1200)
    return await offsite_page(page)


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
    next_page = await offsite_page(next_page)
    await dismiss_overlays(next_page)
    if detect_ats(next_page.url) != "unknown":
        return next_page
    offsite = await _extract_offsite_url(next_page, jd_text)
    if offsite and detect_ats(offsite) != "unknown":
        await next_page.goto(offsite, wait_until="domcontentloaded", timeout=45000)
        await wait_settled(next_page)
        return next_page
    return await offsite_page(next_page)


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
    report=None,
) -> dict:
    from backend.applier.filler import (
        fill_form,
        finish_application,
        noop_report,
        screenshot_failure,
        unfilled_required,
        upload_resume,
        wait_settled,
    )

    report = report or noop_report
    from pathlib import Path

    log_dir = Path(__file__).resolve().parent.parent.parent / "data" / "apply_logs"
    btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
    try:
        await btn.click(timeout=4000)
    except Exception:
        report("error", "Easy Apply button not clickable", False)
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
        report("upload", "resume attached", True)
    extra = await fill_form(page, profile, job_title, company)
    info["filled"] += extra.get("filled", 0)
    info["unknown_required"] = extra.get("unknown_required") or []
    report("fill", f"{info['filled']} fields", bool(info["filled"]))

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
        report("next", "advanced Easy Apply step", True)
        await wait_settled(page, 900)
        extra = await fill_form(page, profile, job_title, company)
        info["filled"] += extra.get("filled", 0)
        if await upload_resume(page, resume, page=page):
            info["resume_uploaded"] = True
    return await finish_application(page, page, profile, auto_submit, job_id, info, log_dir)

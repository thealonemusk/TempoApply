"""ATS-specific apply flows. Greenhouse, Lever, Workday, plus custom/generic."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

from loguru import logger
from playwright.async_api import Page

from backend.applier.ats import detect_ats, first_ats_url
from backend.applier.filler import (
    application_frame,
    application_succeeded,
    apply_result,
    captcha_present,
    click_apply,
    click_named_button,
    click_next,
    click_submit,
    dismiss_overlays,
    fill_form,
    finish_application,
    screenshot_failure,
    unfilled_required,
    upload_resume,
    wait_settled,
)
from backend.applier.linkedin_apply import (
    apply_linkedin_easy,
    offsite_page,
    open_from_linkedin,
    page_opened_since,
)
from backend.applier.profile import ApplicantProfile
from backend.applier.workday import apply_workday

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "apply_logs"


def _result(status: str, message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return apply_result(status, message, extra)


async def _goto(page: Page, url: str) -> None:
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    await wait_settled(page)
    await dismiss_overlays(page)


async def _finish(
    page: Page,
    scope,
    profile: ApplicantProfile,
    auto_submit: bool,
    job_id: str,
    filled_info: Dict[str, Any],
) -> Dict[str, Any]:
    return await finish_application(page, scope, profile, auto_submit, job_id, filled_info, LOG_DIR)


async def apply_greenhouse(
    page: Page,
    profile: ApplicantProfile,
    resume: Path,
    job_title: str,
    company: str,
    auto_submit: bool,
    job_id: str,
) -> Dict[str, Any]:
    await dismiss_overlays(page)
    await click_apply(page)
    await wait_settled(page)
    scope = await application_frame(page)
    uploaded = await upload_resume(scope, resume, page=page)
    info = await fill_form(scope, profile, job_title, company)
    info["resume_uploaded"] = uploaded
    for label, value in (
        ("First Name", profile.first_name),
        ("Last Name", profile.last_name),
        ("Email", profile.email),
        ("Phone", profile.phone_national() or profile.phone),
        ("LinkedIn Profile", profile.linkedin),
        ("Country", profile.country),
        ("Location (City)", profile.city),
    ):
        if not value:
            continue
        loc = scope.get_by_label(label, exact=False)
        try:
            if not await loc.count():
                continue
            current = ""
            try:
                current = await loc.first.input_value()
            except Exception:
                pass
            if current.strip():
                continue
            await loc.first.fill(value)
            info["filled"] = info.get("filled", 0) + 1
        except Exception:
            try:
                await loc.first.select_option(label=value)
                info["filled"] = info.get("filled", 0) + 1
            except Exception:
                continue
    # Known Greenhouse ids if generic pass missed them
    for sel, value in (
        ("#first_name", profile.first_name),
        ("#last_name", profile.last_name),
        ("#email", profile.email),
        ("#phone", profile.phone_e164() or profile.phone),
        ('input[name="job_application[first_name]"]', profile.first_name),
        ('input[name="job_application[last_name]"]', profile.last_name),
        ('input[name="job_application[email]"]', profile.email),
        ('input[name="job_application[phone]"]', profile.phone_e164() or profile.phone),
        ('input[name="job_application[linkedin]"]', profile.linkedin),
        ("#linkedin", profile.linkedin),
    ):
        loc = scope.locator(sel)
        try:
            if await loc.count() and not (await loc.first.input_value()).strip() and value:
                await loc.first.fill(value)
                info["filled"] = info.get("filled", 0) + 1
        except Exception:
            continue
    loc_input = scope.locator('#job_application_location, input[name="job_application[location]"]')
    try:
        if await loc_input.count() and profile.location_string():
            current = await loc_input.first.input_value()
            if not current.strip():
                await loc_input.first.fill(profile.location_string())
                await page.wait_for_timeout(700)
                opt = scope.locator('[role="option"], .autocomplete-result, ul li').filter(
                    has_text=profile.city or profile.country
                )
                if await opt.count():
                    await opt.first.click()
    except Exception:
        pass
    return await _finish(page, scope, profile, auto_submit, job_id, info)


async def apply_lever(
    page: Page,
    profile: ApplicantProfile,
    resume: Path,
    job_title: str,
    company: str,
    auto_submit: bool,
    job_id: str,
) -> Dict[str, Any]:
    url = page.url
    apply = apply_url_for_ats(url, "lever")
    if "/apply" not in url:
        await _goto(page, apply)
    await dismiss_overlays(page)
    uploaded = await upload_resume(page, resume, page=page)
    info = await fill_form(page, profile, job_title, company)
    info["resume_uploaded"] = uploaded
    named = {
        'input[name="name"]': profile.full_name,
        'input[name="email"]': profile.email,
        'input[name="phone"]': profile.phone_e164() or profile.phone,
        'input[name="org"]': profile.current_company,
        'input[name="urls[LinkedIn]"]': profile.linkedin,
        'input[name="urls[GitHub]"]': profile.github,
        'input[name="urls[Portfolio]"]': profile.portfolio,
        'input[name="urls[Other]"]': profile.portfolio or profile.github,
        "textarea[name='comments']": profile.cover_letter(job_title, company),
        "textarea[name='additionalInformation']": profile.cover_letter(job_title, company),
    }
    for sel, value in named.items():
        if not value:
            continue
        loc = page.locator(sel)
        try:
            if await loc.count():
                current = await loc.first.input_value() if "textarea" not in sel else await loc.first.inner_text()
                if not (current or "").strip():
                    await loc.first.fill(value)
                    info["filled"] = info.get("filled", 0) + 1
        except Exception:
            continue
    boxes = page.locator('input[type="checkbox"][required], input[name*="consent"]')
    try:
        box_count = await boxes.count()
    except Exception:
        box_count = 0
    for i in range(box_count):
        box = boxes.nth(i)
        try:
            if not await box.is_checked():
                await box.check()
        except Exception:
            continue
    return await _finish(page, page, profile, auto_submit, job_id, info)


async def follow_external_apply(page: Page) -> tuple[Page, str]:
    """From an aggregator or career posting, follow company-site apply if present."""
    ats = detect_ats(page.url)
    if ats in {"greenhouse", "lever", "workday", "ashby"}:
        return page, ats

    try:
        found = first_ats_url(await page.content())
        if found:
            await _goto(page, found)
            return page, detect_ats(page.url) or "custom"
    except Exception:
        pass

    selectors = [
        'a[href*="greenhouse.io"]',
        'a[href*="jobs.lever.co"]',
        'a[href*="myworkdayjobs.com"]',
        'a[href*="ashbyhq.com"]',
        'a[href*="smartrecruiters.com"]',
        'a.apply-button',
        'a[data-tracking-control-name*="apply"]',
        'a:has-text("Apply on company website")',
        'a:has-text("Apply on company")',
        'a:has-text("company website")',
        'a:has-text("Apply now")',
        'a:has-text("Apply Now")',
        'button:has-text("Apply now")',
        'button:has-text("Apply Now")',
        'button:has-text("Apply")',
        'a:has-text("Apply")',
    ]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if not await loc.count() or not await loc.first.is_visible():
                continue
            text = ((await loc.first.inner_text()) or "").lower()
            if "easy apply" in text:
                continue
            href = await loc.first.get_attribute("href")
            existing = list(page.context.pages)
            if href:
                target = urljoin(page.url, href)
                if urlparse(target).netloc and urlparse(target).netloc != urlparse(page.url).netloc:
                    await _goto(page, target)
                    return page, detect_ats(page.url) or "custom"
            await loc.first.click()
            opened = await page_opened_since(page.context, existing, timeout_ms=10000)
            if opened:
                page = opened
            else:
                await wait_settled(page, 1200)
                page = await offsite_page(page)
            return page, detect_ats(page.url) or "custom"
        except Exception:
            continue

    existing = list(page.context.pages)
    clicked = await click_apply(page)
    if clicked:
        opened = await page_opened_since(page.context, existing, timeout_ms=10000)
        if opened:
            page = opened
        else:
            await wait_settled(page, 1200)
            page = await offsite_page(page)
        return page, detect_ats(page.url) or "custom"
    return page, detect_ats(page.url) or "custom"


async def apply_custom(
    page: Page,
    profile: ApplicantProfile,
    resume: Path,
    job_title: str,
    company: str,
    auto_submit: bool,
    job_id: str,
) -> Dict[str, Any]:
    await dismiss_overlays(page)
    existing = list(page.context.pages)
    await click_apply(page)
    opened = await page_opened_since(page.context, existing, timeout_ms=10000)
    if opened:
        page = opened
        await dismiss_overlays(page)
    else:
        await wait_settled(page)
        page = await offsite_page(page)
    ats = detect_ats(page.url)
    if ats == "workday":
        return await apply_workday(page, profile, resume, job_title, company, auto_submit, job_id)
    if ats == "greenhouse":
        return await apply_greenhouse(page, profile, resume, job_title, company, auto_submit, job_id)
    if ats == "lever":
        return await apply_lever(page, profile, resume, job_title, company, auto_submit, job_id)
    scope = await application_frame(page)
    uploaded = await upload_resume(scope, resume, page=page)
    info = await fill_form(scope, profile, job_title, company)
    info["resume_uploaded"] = uploaded
    # Multi-step generic wizards
    for _ in range(6):
        leftover = await unfilled_required(scope)
        submit_visible = False
        try:
            submit_visible = await scope.get_by_role("button", name="Submit", exact=False).count() > 0
        except Exception:
            pass
        if submit_visible and not leftover:
            break
        moved = await click_next(scope)
        if not moved:
            break
        await wait_settled(page)
        extra = await fill_form(scope, profile, job_title, company)
        info["filled"] += extra.get("filled", 0)
        if await upload_resume(scope, resume, page=page):
            info["resume_uploaded"] = True
    return await _finish(page, scope, profile, auto_submit, job_id, info)


async def apply_on_page(
    page: Page,
    url: str,
    profile: ApplicantProfile,
    resume: Path,
    job_title: str,
    company: str,
    auto_submit: bool,
    job_id: str,
    jd_text: str = "",
) -> Dict[str, Any]:
    await _goto(page, url)
    page = await open_from_linkedin(page, jd_text)
    page = await offsite_page(page)
    page, ats = await follow_external_apply(page)
    page = await offsite_page(page)
    logger.info(f"Applying via ATS={ats} url={page.url}")

    if ats == "unknown" and "linkedin.com" in (page.url or "").lower():
        from backend.applier.linkedin_apply import _is_easy_apply

        if await _is_easy_apply(page):
            result = await apply_linkedin_easy(
                page, profile, resume, job_title, company, auto_submit, job_id
            )
            result["final_url"] = page.url
            return result
        await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
        return _result(
            "needs_review",
            "Could not open the company application from LinkedIn. Open this one manually.",
            {"ats": "unknown", "final_url": page.url},
        )

    handlers = {
        "greenhouse": apply_greenhouse,
        "lever": apply_lever,
        "workday": apply_workday,
        "ashby": apply_custom,
        "custom": apply_custom,
        "unknown": apply_custom,
    }
    handler = handlers.get(ats, apply_custom)
    result = await handler(page, profile, resume, job_title, company, auto_submit, job_id)
    result["ats"] = ats
    result["final_url"] = page.url
    return result

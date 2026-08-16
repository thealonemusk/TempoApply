"""ATS-specific apply flows. Greenhouse, Lever, Workday, plus custom/generic."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

from loguru import logger
from playwright.async_api import Page

from backend.applier.ats import apply_url_for_ats, detect_ats
from backend.applier.filler import (
    application_frame,
    application_succeeded,
    captcha_present,
    click_apply,
    click_named_button,
    click_next,
    click_submit,
    dismiss_overlays,
    fill_form,
    screenshot_failure,
    unfilled_required,
    upload_resume,
    wait_settled,
)
from backend.applier.profile import ApplicantProfile

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "apply_logs"

WORKDAY_IDS = {
    "legalNameSection_firstName": "first_name",
    "legalNameSection_lastName": "last_name",
    "addressSection_addressLine1": "address_line1",
    "addressSection_addressLine2": "address_line2",
    "addressSection_city": "city",
    "addressSection_postalCode": "postal_code",
    "email": "email",
    "phone-number": "phone",
}


def _result(status: str, message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {"status": status, "message": message}
    if extra:
        out.update(extra)
    return out


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
    if await application_succeeded(page):
        return _result("applied", "Application submitted", filled_info)

    leftover = await unfilled_required(scope)
    leftover += filled_info.get("unknown_required") or []
    leftover = [x for x in leftover if x]
    filled = int(filled_info.get("filled") or 0)
    uploaded = bool(filled_info.get("resume_uploaded"))

    if filled == 0 and not uploaded:
        await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
        return _result("failed", "No application form was found or filled on this posting", filled_info)

    if leftover:
        await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
        return _result(
            "needs_review",
            "Required fields could not be filled: " + "; ".join(leftover[:8]),
            filled_info,
        )

    if not auto_submit or not profile.auto_submit:
        await screenshot_failure(page, LOG_DIR / f"{job_id}-filled.png")
        return _result("needs_review", "Form filled. auto_submit is off — submit manually.", filled_info)

    if await captcha_present(page):
        await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
        return _result("needs_review", "CAPTCHA present — complete this one in the browser", filled_info)

    clicked = await click_submit(scope)
    await wait_settled(page, 1500)
    if await application_succeeded(page):
        return _result("applied", "Application submitted", filled_info)
    if clicked:
        await wait_settled(page, 2000)
        if await application_succeeded(page):
            return _result("applied", "Application submitted", filled_info)
        await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
        return _result(
            "needs_review",
            "Submit clicked but confirmation was not detected. Check the screenshot.",
            filled_info,
        )
    await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
    return _result("needs_review", "Could not find a submit button", filled_info)


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


async def _workday_typeahead(page: Page, automation_id: str, value: str) -> bool:
    if not value:
        return False
    loc = page.locator(f'[data-automation-id="{automation_id}"]')
    try:
        if not await loc.count():
            return False
        await loc.first.click()
        await loc.first.fill("")
        await loc.first.fill(value)
        await page.wait_for_timeout(700)
        opt = page.locator(
            '[data-automation-id="promptLeafNode"], [role="option"], [data-automation-id="promptOption"]'
        )
        if await opt.count():
            match = opt.filter(has_text=value)
            await (match.first if await match.count() else opt.first).click()
            return True
        await loc.first.press("Enter")
        return True
    except Exception as exc:
        logger.debug(f"Workday typeahead {automation_id}: {exc}")
        return False


async def _workday_fill_known(page: Page, profile: ApplicantProfile) -> int:
    filled = 0
    values = {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "address_line1": profile.address_line1 or profile.city,
        "address_line2": profile.address_line2,
        "city": profile.city,
        "postal_code": profile.postal_code,
        "email": profile.email,
        "phone": profile.phone_national() or profile.phone,
    }
    for auto_id, key in WORKDAY_IDS.items():
        val = values.get(key, "")
        if not val:
            continue
        loc = page.locator(f'[data-automation-id="{auto_id}"]')
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
            await loc.first.click()
            await loc.first.fill(val)
            filled += 1
        except Exception:
            continue

    await _workday_typeahead(page, "addressSection_country", profile.country)
    if profile.state:
        await _workday_typeahead(page, "addressSection_countryRegion", profile.state)
    await _workday_typeahead(page, "phone-device-type", "Mobile")
    how = page.locator('[data-automation-id="sourcePrompt"], [data-automation-id*="howDidYouHear"]')
    try:
        if await how.count():
            await _workday_typeahead(page, "sourcePrompt", profile.how_heard)
    except Exception:
        pass
    return filled


async def _workday_sign_in(page: Page) -> bool:
    from backend.config import settings

    email = (settings.workday_email or "").strip()
    password = (settings.workday_password or "").strip()
    if not email or not password:
        return False

    name = page.locator('[data-automation-id="legalNameSection_firstName"]')
    try:
        if await name.count() and await name.first.is_visible():
            return True
    except Exception:
        pass

    for sel in (
        '[data-automation-id="signInLink"]',
        'button[data-automation-id="signIn"]',
        'a[data-automation-id="signIn"]',
    ):
        loc = page.locator(sel)
        try:
            if await loc.count() and await loc.first.is_visible():
                await loc.first.click()
                await wait_settled(page, 1200)
                break
        except Exception:
            continue
    else:
        sign_in = page.get_by_role("button", name="Sign In", exact=True)
        try:
            if await sign_in.count() and await sign_in.first.is_visible():
                await sign_in.first.click()
                await wait_settled(page, 1200)
        except Exception:
            pass

    email_loc = page.locator(
        '[data-automation-id="email"], input[type="email"], input[autocomplete="username"]'
    )
    pwd_loc = page.locator('[data-automation-id="password"], input[type="password"]')
    try:
        if not await email_loc.count() or not await pwd_loc.count():
            return bool(await name.count() and await name.first.is_visible())
        if not await pwd_loc.first.is_visible():
            return bool(await name.count() and await name.first.is_visible())
        await email_loc.first.fill(email)
        await pwd_loc.first.fill(password)
        submit = page.locator('[data-automation-id="signInSubmitButton"]')
        if await submit.count() and await submit.first.is_visible():
            await submit.first.click()
        else:
            await click_named_button(page, ("Sign In",), timeout=2500)
        await wait_settled(page, 3000)
        try:
            loader = page.locator('[data-automation-id="loading"]')
            if await loader.count():
                await loader.first.wait_for(state="hidden", timeout=20000)
        except Exception:
            pass
        try:
            if await pwd_loc.count() and await pwd_loc.first.is_visible():
                return False
        except Exception:
            pass
        return True
    except Exception:
        return False


async def apply_workday(
    page: Page,
    profile: ApplicantProfile,
    resume: Path,
    job_title: str,
    company: str,
    auto_submit: bool,
    job_id: str,
) -> Dict[str, Any]:
    await dismiss_overlays(page)
    try:
        loader = page.locator('[data-automation-id="loading"]')
        if await loader.count():
            await loader.first.wait_for(state="hidden", timeout=25000)
    except Exception:
        pass
    try:
        await page.wait_for_selector(
            '[data-automation-id="jobPostingApplyButton"], '
            '[data-automation-id="adventureButton"], '
            '[data-automation-id="jobPostingPageApplyButton"], '
            'button:has-text("Apply")',
            timeout=20000,
        )
    except Exception:
        pass
    for _ in range(4):
        cookie = page.locator('#onetrust-accept-btn-handler, button:has-text("Accept All Cookies"), button:has-text("Accept Cookies")')
        try:
            if await cookie.count() and await cookie.first.is_visible():
                await cookie.first.click(timeout=2000)
                await page.wait_for_timeout(400)
                break
        except Exception:
            pass
        await page.wait_for_timeout(300)
    clicked = False
    for sel in (
        '[data-automation-id="jobPostingApplyButton"]',
        '[data-automation-id="adventureButton"]',
        '[data-automation-id="jobPostingPageApplyButton"]',
        'button[data-automation-id="jobPostingApplyButton"]',
    ):
        loc = page.locator(sel)
        try:
            if await loc.count() and await loc.first.is_visible():
                try:
                    await loc.first.click(timeout=4000)
                except Exception:
                    await loc.first.click(timeout=4000, force=True)
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        for role, exact in (("button", True), ("link", True), ("button", False), ("link", False)):
            loc = page.get_by_role(role, name="Apply", exact=exact)
            try:
                n = await loc.count()
            except Exception:
                continue
            for i in range(n):
                btn = loc.nth(i)
                try:
                    if not await btn.is_visible():
                        continue
                    text = (await btn.inner_text()).strip().lower()
                    if text != "apply" and exact:
                        continue
                    if "sign" in text:
                        continue
                    await btn.click(timeout=4000)
                    clicked = True
                    break
                except Exception:
                    continue
            if clicked:
                break
    if not clicked:
        clicked = await page.evaluate(
            """() => {
                const ids = ['jobPostingApplyButton','adventureButton','jobPostingPageApplyButton'];
                for (const id of ids) {
                    const el = document.querySelector(`[data-automation-id="${id}"]`);
                    if (el) { el.click(); return true; }
                }
                const btns = Array.from(document.querySelectorAll('button, a'));
                const apply = btns.find(e => (e.innerText || '').trim() === 'Apply' && e.offsetParent);
                if (apply) { apply.click(); return true; }
                return false;
            }"""
        )
    await wait_settled(page, 2000)
    try:
        await page.wait_for_selector(
            '[data-automation-id="legalNameSection_firstName"], '
            'input[type="password"], '
            '[data-automation-id="applyManually"], '
            '[data-automation-id="file-upload-input-ref"]',
            timeout=10000,
        )
    except Exception:
        pass

    for name in ("Apply Manually", "Start New Application"):
        loc = page.get_by_role("button", name=name, exact=False)
        try:
            if await loc.count() and await loc.first.is_visible():
                await loc.first.click()
                await wait_settled(page)
                break
        except Exception:
            continue
    loc = page.locator('[data-automation-id="applyManually"]')
    try:
        if await loc.count() and await loc.first.is_visible():
            await loc.first.click()
            await wait_settled(page)
    except Exception:
        pass

    for name in ("Autofill with Resume", "Apply with Resume"):
        loc = page.get_by_role("button", name=name, exact=False)
        try:
            if await loc.count() and await loc.first.is_visible():
                async with page.expect_file_chooser(timeout=4000) as chooser_info:
                    await loc.first.click()
                chooser = await chooser_info.value
                await chooser.set_files(str(resume))
                await wait_settled(page, 1500)
                break
        except Exception:
            continue

    signed_in = await _workday_sign_in(page)
    if not signed_in:
        pwd = page.locator('input[type="password"]')
        account_wall = False
        try:
            account_wall = await pwd.count() > 0 and await pwd.first.is_visible()
        except Exception:
            pass
        if not account_wall:
            try:
                body = (await page.inner_text("body")).lower()
                account_wall = "create account" in body and ("sign in" in body or "my information" in body)
            except Exception:
                pass
        if account_wall:
            await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
            return _result(
                "needs_review",
                "Workday sign-in failed. Apply this one manually.",
            )

    info: Dict[str, Any] = {"filled": 0, "unknown_required": [], "resume_uploaded": False}
    for step in range(12):
        if await application_succeeded(page):
            return _result("applied", "Application submitted", info)
        uploaded = await upload_resume(page, resume, page=page)
        if uploaded:
            info["resume_uploaded"] = True
        info["filled"] += await _workday_fill_known(page, profile)
        generic = await fill_form(page, profile, job_title, company)
        info["filled"] += generic.get("filled", 0)
        info["unknown_required"] = generic.get("unknown_required") or []

        leftover = await unfilled_required(page)
        submit_btn = page.locator(
            '[data-automation-id="bottom-navigation-submit-button"], [data-automation-id="pageFooterSubmitButton"]'
        )
        can_submit = False
        try:
            can_submit = await submit_btn.count() > 0 and await submit_btn.first.is_visible()
        except Exception:
            pass

        if can_submit:
            return await _finish(page, page, profile, auto_submit, job_id, info)

        if leftover:
            # Try next anyway — Workday sometimes marks fields required after blur
            pass
        moved = await click_next(page)
        await wait_settled(page, 1100)
        if not moved:
            return await _finish(page, page, profile, auto_submit, job_id, info)
        logger.info(f"Workday next page ({step + 1}) for {job_title}")

    await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
    return _result("needs_review", "Workday wizard exceeded step limit", info)


async def follow_external_apply(page: Page) -> str:
    """From an aggregator posting, follow company-site apply if present. Returns ATS type."""
    ats = detect_ats(page.url)
    if ats in {"greenhouse", "lever", "workday", "ashby"}:
        return ats

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
    ]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if not await loc.count():
                continue
            href = await loc.first.get_attribute("href")
            if href:
                target = urljoin(page.url, href)
                if urlparse(target).netloc and urlparse(target).netloc != urlparse(page.url).netloc:
                    await _goto(page, target)
                    return detect_ats(page.url) or "custom"
            await loc.first.click()
            await wait_settled(page, 1200)
            return detect_ats(page.url) or "custom"
        except Exception:
            continue

    clicked = await click_apply(page)
    if clicked:
        await wait_settled(page, 1200)
        return detect_ats(page.url) or "custom"
    return detect_ats(page.url) or "custom"


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
    await click_apply(page)
    await wait_settled(page)
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
) -> Dict[str, Any]:
    await _goto(page, url)
    ats = await follow_external_apply(page)
    logger.info(f"Applying via ATS={ats} url={page.url}")

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

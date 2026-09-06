"""Workday candidate apply: sign-in (same email/password on every tenant) then wizard fill."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from loguru import logger
from playwright.async_api import Page

from backend.applier.ats import detect_ats
from backend.applier.creds import workday_credentials
from backend.applier.fields import resolve_value
from backend.applier.filler import (
    application_succeeded,
    captcha_present,
    click_named_button,
    click_next,
    click_submit,
    dismiss_overlays,
    fill_form,
    finish_application,
    noop_report,
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

ALREADY_APPLIED = (
    "you have already applied",
    "already applied to this job",
    "you previously applied",
)


def _result(status: str, message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {"status": status, "message": message, "ats": "workday"}
    if extra:
        out.update(extra)
    return out


SHELL_SEL = (
    '[data-automation-id="utilityButtonSignIn"], '
    '[data-automation-id="utilityButtonSignOut"], '
    '[data-automation-id="adventureButton"], '
    '[data-automation-id="jobPostingApplyButton"], '
    '[data-automation-id="email"], '
    'input[type="password"]'
)


async def _wait_ready(page: Page, ms: int = 1200, shell: bool = False) -> None:
    await dismiss_overlays(page)
    try:
        loader = page.locator(
            '[data-automation-id="loading"], [data-automation-id="busyIndicator"], '
            '[data-automation-id="loadingPage"], [data-automation-id="applyFlowLoadingPage"], '
            '[aria-busy="true"]'
        )
        if await loader.count():
            await loader.first.wait_for(state="hidden", timeout=25000)
    except Exception:
        pass
    if shell:
        try:
            await page.wait_for_selector(SHELL_SEL, timeout=25000)
        except Exception:
            pass
    await wait_settled(page, ms)
    await dismiss_overlays(page)
    try:
        loading_copy = page.get_by_text("Loading", exact=True)
        if await loading_copy.count() and await loading_copy.first.is_visible():
            await loading_copy.first.wait_for(state="hidden", timeout=20000)
    except Exception:
        pass


async def _wait_form(page: Page) -> bool:
    try:
        try:
            loader = page.locator('[data-automation-id="applyFlowLoadingPage"]')
            if await loader.count():
                await loader.first.wait_for(state="hidden", timeout=25000)
        except Exception:
            pass
        try:
            await page.wait_for_selector(
                '[data-automation-id^="formField-"], '
                '[data-automation-id="legalNameSection_firstName"]',
                timeout=20000,
                state="visible",
            )
            return True
        except Exception:
            return False
        return True
    except Exception:
        return False


async def _click_next(page: Page) -> bool:
    wd = page.locator(
        '[data-automation-id="bottom-navigation-next-button"], '
        '[data-automation-id="pageFooterNextButton"]'
    )
    if await _visible(wd):
        try:
            if await wd.first.is_disabled():
                return False
            if (await wd.first.get_attribute("aria-disabled") or "").lower() == "true":
                return False
        except Exception:
            pass
        await wd.first.click(timeout=3000)
        return True
    return await click_next(page)


def _login_url(job_url: str) -> str:
    parsed = urlparse(job_url)
    parts = [p for p in parsed.path.split("/") if p]
    site = []
    for part in parts:
        if part.lower() in {"job", "jobs", "login", "apply", "userhome", "en-us", "en-gb"}:
            if part.lower() in {"en-us", "en-gb"}:
                site.append(part)
                continue
            break
        site.append(part)
    if not site:
        return f"{parsed.scheme}://{parsed.netloc}/login"
    return f"{parsed.scheme}://{parsed.netloc}/{'/'.join(site)}/login"


async def _visible(locator) -> bool:
    try:
        return await locator.count() > 0 and await locator.first.is_visible()
    except Exception:
        return False


async def _type_value(locator, value: str) -> bool:
    try:
        await locator.click(timeout=4000)
        await locator.fill("")
        await locator.fill(value)
        try:
            current = await locator.input_value()
            if current.strip() == value.strip():
                return True
        except Exception:
            pass
        await locator.press("Control+A")
        await locator.press_sequentially(value, delay=20)
        return True
    except Exception:
        return False


async def _auth_scope(page: Page):
    """Workday often puts Sign In in a child frame."""
    candidates = [page, *page.frames]
    for scope in candidates:
        try:
            pwd = scope.locator('[data-automation-id="password"], input[type="password"]')
            if await _visible(pwd):
                return scope
        except Exception:
            continue
    return page


async def _signed_in(page: Page) -> bool:
    for sel in (
        '[data-automation-id="utilityButtonSignOut"]',
        '[data-automation-id="utilityButtonAccount"]',
        'button:has-text("Sign Out")',
        'a:has-text("Sign Out")',
    ):
        if await _visible(page.locator(sel)):
            return True
    try:
        body = (await page.inner_text("body")).lower()
    except Exception:
        body = ""
    if "sign out" in body:
        return True
    name = page.locator('[data-automation-id="legalNameSection_firstName"]')
    pwd = page.locator('input[type="password"]')
    try:
        if await _visible(name) and not await _visible(pwd):
            return True
    except Exception:
        pass
    return False


async def _login_form_visible(page: Page) -> bool:
    scope = await _auth_scope(page)
    pwd = scope.locator('[data-automation-id="password"], input[type="password"]')
    return await _visible(pwd)


async def _open_sign_in(page: Page) -> None:
    if await _login_form_visible(page):
        return
    for sel in (
        '[data-automation-id="utilityButtonSignIn"]',
        '[data-automation-id="signInLink"]',
        '[data-automation-id="linkButtonSignIn"]',
        'button[data-automation-id="signIn"]',
        'a[data-automation-id="signIn"]',
    ):
        loc = page.locator(sel)
        if await _visible(loc):
            try:
                await loc.first.click(timeout=3000)
                await _wait_ready(page, 1500)
                if await _login_form_visible(page):
                    return
            except Exception:
                continue
    await click_named_button(page, ("Sign In",), timeout=2500)
    await _wait_ready(page, 1500)


async def _switch_to_sign_in_tab(scope) -> None:
    verify = scope.locator(
        '[data-automation-id="verifyPassword"], [data-automation-id="confirmPassword"], '
        'input[autocomplete="new-password"]'
    )
    create_btn = scope.locator(
        '[data-automation-id="createAccountSubmitButton"], button:has-text("Create Account")'
    )
    on_create = await _visible(verify) or await _visible(create_btn)
    if not on_create:
        return
    for sel in (
        '[data-automation-id="signInLink"]',
        '[data-automation-id="clickSignIn"]',
        'button:has-text("Sign In")',
        'a:has-text("Sign In")',
        'a:has-text("Already have an account")',
    ):
        loc = scope.locator(sel)
        if await _visible(loc):
            try:
                await loc.first.click(timeout=2500)
                await scope.wait_for_timeout(800)
                return
            except Exception:
                continue


async def ensure_signed_in(page: Page) -> bool:
    email, password = workday_credentials()
    if await _signed_in(page):
        return True
    if not email or not password:
        logger.error("Workday email/password missing from config/.env")
        return False

    await _open_sign_in(page)
    if not await _login_form_visible(page):
        try:
            await page.goto(_login_url(page.url), wait_until="domcontentloaded", timeout=45000)
            await _wait_ready(page, 1500, shell=True)
        except Exception:
            pass
        await _open_sign_in(page)

    if not await _login_form_visible(page):
        return await _signed_in(page)

    scope = await _auth_scope(page)
    await _switch_to_sign_in_tab(scope)
    scope = await _auth_scope(page)

    email_loc = scope.locator(
        '[data-automation-id="email"], input[type="email"], input[autocomplete="username"]'
    ).first
    pwd_loc = scope.locator('[data-automation-id="password"], input[type="password"]').first
    if not await _type_value(email_loc, email):
        return False
    if not await _type_value(pwd_loc, password):
        return False

    submit = scope.locator('[data-automation-id="signInSubmitButton"]')
    if await _visible(submit):
        try:
            await submit.first.click(timeout=4000)
        except Exception:
            await click_named_button(page, ("Sign In",), timeout=3000)
    else:
        await click_named_button(page, ("Sign In",), timeout=3000)

    await _wait_ready(page, 2500)
    try:
        await page.wait_for_function(
            """() => {
                const pwd = document.querySelector('[data-automation-id="password"], input[type="password"]');
                const out = document.querySelector(
                    '[data-automation-id="utilityButtonSignOut"], [data-automation-id="legalNameSection_firstName"]'
                );
                const apply = document.querySelector(
                    '[data-automation-id="jobPostingApplyButton"], [data-automation-id="adventureButton"]'
                );
                if (out || apply) return true;
                if (pwd && pwd.offsetParent) return false;
                return true;
            }""",
            timeout=20000,
        )
    except Exception:
        pass
    await _wait_ready(page, 800)

    if await _login_form_visible(page) and not await _signed_in(page):
        try:
            alert = await page.inner_text("body")
            logger.warning(f"Workday sign-in still showing password field: {alert[:180]}")
        except Exception:
            pass
        return False
    return True


async def _click_apply(page: Page) -> bool:
    await _wait_ready(page, 400, shell=True)
    loc = page.locator('[data-automation-id="adventureButton"], [data-automation-id="jobPostingApplyButton"]')
    if await _visible(loc):
        href = await loc.first.get_attribute("href")
        if href:
            from urllib.parse import urljoin
            target = urljoin(page.url, href)
            try:
                await page.goto(target, wait_until="domcontentloaded", timeout=45000)
                await _wait_ready(page, 1500)
                return True
            except Exception:
                pass
        try:
            await loc.first.click(timeout=4000)
            await _wait_ready(page, 1800)
            return True
        except Exception:
            try:
                await loc.first.click(timeout=4000, force=True)
                await _wait_ready(page, 1800)
                return True
            except Exception:
                pass
    if "/apply" not in (page.url or "").lower():
        apply_url = page.url.split("?")[0].rstrip("/") + "/apply"
        try:
            await page.goto(apply_url, wait_until="domcontentloaded", timeout=45000)
            await _wait_ready(page, 1500)
            return True
        except Exception:
            pass
    for role, exact in (("button", True), ("link", True), ("button", False)):
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
                if "sign" in text or "linkedin" in text:
                    continue
                if exact and text != "apply":
                    continue
                await btn.click(timeout=4000)
                await _wait_ready(page, 1800)
                return True
            except Exception:
                continue
    return False


async def _start_application(page: Page, resume: Path) -> None:
    try:
        await page.wait_for_selector(
            '[data-automation-id="useMyLastApplication"], '
            '[data-automation-id="applyManually"], '
            '[data-automation-id="legalNameSection_firstName"], '
            '[data-automation-id*="formField"], '
            'button:has-text("Use My Last Application"), '
            'button:has-text("Apply Manually"), '
            'button:has-text("Autofill with Resume")',
            timeout=20000,
        )
    except Exception:
        pass

    for sel in (
        '[data-automation-id="useMyLastApplication"]',
        '[data-automation-id="applyManually"]',
        '[data-automation-id="applyManuallyButton"]',
    ):
        loc = page.locator(sel)
        if await _visible(loc):
            try:
                await loc.first.click(timeout=3000)
                await _wait_ready(page, 1500)
            except Exception:
                pass
            break
    else:
        for name in ("Use My Last Application", "Apply Manually", "Start New Application"):
            loc = page.get_by_text(name, exact=False)
            if await _visible(loc):
                try:
                    await loc.first.click(timeout=3000)
                    await _wait_ready(page, 1500)
                except Exception:
                    pass
                break

    for name in ("Autofill with Resume", "Apply with Resume"):
        loc = page.get_by_role("button", name=name, exact=False)
        if await _visible(loc):
            try:
                async with page.expect_file_chooser(timeout=5000) as chooser_info:
                    await loc.first.click()
                chooser = await chooser_info.value
                await chooser.set_files(str(resume))
                await _wait_ready(page, 1500)
            except Exception:
                pass
            break


async def _typeahead(page: Page, automation_id: str, value: str) -> bool:
    if not value:
        return False
    loc = page.locator(f'[data-automation-id="{automation_id}"]')
    if not await _visible(loc):
        return False
    try:
        await loc.first.click()
        await _type_value(loc.first, value)
        await page.wait_for_timeout(600)
        opt = page.locator(
            '[data-automation-id="promptLeafNode"], [data-automation-id="promptOption"], [role="option"]'
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


async def _fill_known(page: Page, profile: ApplicantProfile) -> int:
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
        if not await _visible(loc):
            continue
        try:
            current = ""
            try:
                current = await loc.first.input_value()
            except Exception:
                pass
            if current.strip():
                continue
            if await _type_value(loc.first, val):
                filled += 1
        except Exception:
            continue

    await _typeahead(page, "addressSection_country", profile.country)
    if profile.state:
        await _typeahead(page, "addressSection_countryRegion", profile.state)
    await _typeahead(page, "phone-device-type", "Mobile")
    await _typeahead(page, "sourcePrompt", profile.how_heard)
    wrap = page.locator('[data-automation-id="formField-source"]')
    if await _visible(wrap):
        try:
            box = wrap.locator('[data-automation-id="multiSelectContainer"]')
            if await _visible(box):
                await box.first.click()
                await page.wait_for_timeout(400)
                typed = profile.how_heard or "Company Website"
                inp = wrap.locator("input")
                if await inp.count():
                    await _type_value(inp.first, typed)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(350)
                await _pick_option(page, typed)
                await page.keyboard.press("Escape")
        except Exception:
            pass
    return filled


async def _widget_label(page: Page, el) -> str:
    for attr in ("aria-label", "aria-labelledby"):
        try:
            val = await el.get_attribute(attr)
        except Exception:
            val = ""
        if val and attr == "aria-label":
            return val.strip()
        if val and attr == "aria-labelledby":
            try:
                text = await page.evaluate(
                    "(id) => (document.getElementById(id) || {}).innerText || ''",
                    val.split()[0],
                )
                if text:
                    return text.strip()
            except Exception:
                pass
    try:
        return await page.evaluate(
            """(el) => {
                const wrap = el.closest('[data-automation-id*="formField"], [class*="FormField"], label, fieldset');
                if (!wrap) return (el.innerText || '').slice(0, 120);
                const lab = wrap.querySelector('label, legend, [data-automation-id$="label"]');
                return ((lab && lab.innerText) || wrap.innerText || '').split('\\n')[0].slice(0, 180);
            }""",
            await el.element_handle(),
        )
    except Exception:
        try:
            return ((await el.inner_text()) or "").strip()
        except Exception:
            return ""


async def _pick_option(page: Page, desired: str) -> bool:
    opt = page.locator(
        '[data-automation-id="promptOption"], [data-automation-id="promptLeafNode"], '
        '[role="option"], [data-automation-id="selectWidget-option"]'
    )
    try:
        count = min(await opt.count(), 40)
    except Exception:
        return False
    want = (desired or "").strip().lower()
    first_visible = None
    for i in range(count):
        item = opt.nth(i)
        try:
            if not await item.is_visible():
                continue
        except Exception:
            continue
        if first_visible is None:
            first_visible = item
        text = ((await item.inner_text()) or "").strip().lower()
        if want and (want == text or want in text or text in want):
            await item.click(timeout=2500)
            return True
        if want in {"yes", "no"} and text.startswith(want):
            await item.click(timeout=2500)
            return True
    if first_visible is not None and want in {"yes", "no"}:
        return False
    if first_visible is not None and count <= 4:
        await first_visible.click(timeout=2500)
        return True
    return False


async def _fill_form_blocks(page: Page, profile: ApplicantProfile, job_title: str, company: str) -> int:
    fields = page.locator('[data-automation-id*="formField"]')
    try:
        n = min(await fields.count(), 30)
    except Exception:
        n = 0
    logger.info(f"Workday formFields={n}")
    filled = 0
    for i in range(n):
        wrap = fields.nth(i)
        try:
            if not await wrap.is_visible():
                continue
            label = ""
            lab = wrap.locator('label, legend, [data-automation-id$="label"]')
            if await lab.count():
                label = ((await lab.first.inner_text()) or "").strip()
            if not label:
                label = ((await wrap.inner_text()) or "").split("\n")[0].strip()
            desired = resolve_value(profile, label, job_title, company)
            if not desired:
                continue
            widget = wrap.locator(
                '[data-automation-id="multiSelectContainer"], '
                '[aria-haspopup="listbox"], [aria-haspopup="true"], [role="combobox"], '
                'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), textarea, button'
            )
            if not await widget.count():
                continue
            el = widget.first
            current = ((await wrap.inner_text()) or "").lower()
            already = (
                "india" in current
                and "country" in label.lower()
            ) or (
                "mobile" in current and "phone device" in label.lower()
            ) or (
                "+91" in current and "phone code" in label.lower()
            )
            if already:
                continue
            tag = (await el.evaluate("e => (e.tagName || '').toLowerCase()")) or ""
            itype = (await el.get_attribute("type") or "").lower()
            if tag in {"input", "textarea"} and itype not in {"checkbox", "radio", "button", "submit"}:
                if await _type_value(el, desired):
                    filled += 1
                continue
            await el.click(timeout=3000)
            await page.wait_for_timeout(500)
            search = page.locator('[data-automation-id="searchBox"], input[placeholder*="Search" i]')
            if await _visible(search):
                await _type_value(search.last, desired)
                await page.wait_for_timeout(400)
            picked = await _pick_option(page, desired)
            if not picked and "hear" in label.lower():
                for opt_name in ("Company Website", "Internet", "Job Board", "LinkedIn"):
                    opt = page.get_by_text(opt_name, exact=True)
                    try:
                        if await opt.count() and await opt.first.is_visible():
                            await opt.first.click(timeout=2000)
                            picked = True
                            break
                    except Exception:
                        continue
            if picked:
                filled += 1
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass
            else:
                await page.keyboard.press("Escape")
        except Exception:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            continue
    return filled


async def _already_applied(page: Page) -> bool:
    try:
        body = (await page.inner_text("body")).lower()
    except Exception:
        return False
    return any(s in body for s in ALREADY_APPLIED)


async def _step_name(page: Page) -> str:
    loc = page.locator('[data-automation-id="progressBarActiveStep"]')
    try:
        if await loc.count():
            return ((await loc.first.inner_text()) or "").strip()
    except Exception:
        pass
    return ""


async def _workday_errors(page: Page) -> list[str]:
    out = []
    loc = page.locator('[data-automation-id="inputAlert"], [data-automation-id="errorListItem"]')
    try:
        n = min(await loc.count(), 10)
    except Exception:
        return out
    for i in range(n):
        try:
            text = ((await loc.nth(i).inner_text()) or "").strip()
            if text:
                out.append(text.split("\n")[0][:120])
        except Exception:
            continue
    return out


async def _submit_visible(page: Page) -> bool:
    loc = page.locator(
        '[data-automation-id="bottom-navigation-submit-button"], '
        '[data-automation-id="pageFooterSubmitButton"]'
    )
    return await _visible(loc)


async def apply_workday(
    page: Page,
    profile: ApplicantProfile,
    resume: Path,
    job_title: str,
    company: str,
    auto_submit: bool,
    job_id: str,
    report=noop_report,
) -> Dict[str, Any]:
    job_url = page.url
    await _wait_ready(page, 800, shell=True)
    signed_in = await ensure_signed_in(page)
    if "login" in (page.url or "").lower() or detect_ats(page.url) != "workday":
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
            await _wait_ready(page, 1000, shell=True)
        except Exception:
            pass
    elif page.url.split("?")[0].rstrip("/") != job_url.split("?")[0].rstrip("/"):
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
            await _wait_ready(page, 1000, shell=True)
        except Exception:
            pass

    report("signin", "signed in" if signed_in else "not signed in", signed_in)

    await _click_apply(page)
    await _wait_ready(page, 1500, shell=True)

    if await _login_form_visible(page):
        signed_in = await ensure_signed_in(page)
        report("signin", "retry after apply click", signed_in)
        if not signed_in:
            await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
            return _result("needs_review", "Workday sign-in failed. Apply this one manually.")

    if await _already_applied(page):
        return _result("applied", "Already applied on this Workday posting")

    await _start_application(page, resume)

    if await _login_form_visible(page) and not signed_in:
        await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
        return _result("needs_review", "Workday sign-in failed. Apply this one manually.")

    info: Dict[str, Any] = {"filled": 0, "unknown_required": [], "resume_uploaded": False}
    for step in range(14):
        if not await _wait_form(page):
            if step == 0:
                await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
                return _result(
                    "needs_review",
                    "Signed into Workday but the application form did not load. Finish this one manually.",
                    info,
                )
            return await finish_application(page, page, profile, auto_submit, job_id, info, LOG_DIR)
        if await application_succeeded(page) or await _already_applied(page):
            return _result("applied", "Application submitted", info)
        if await upload_resume(page, resume, page=page):
            info["resume_uploaded"] = True
            report("upload", "resume attached", True)
        before_fill = info["filled"]
        info["filled"] += await _fill_known(page, profile)
        info["filled"] += await _fill_form_blocks(page, profile, job_title, company)
        generic = await fill_form(page, profile, job_title, company)
        info["filled"] += generic.get("filled", 0)
        info["unknown_required"] = generic.get("unknown_required") or []
        step_label = await _step_name(page) or f"step {step + 1}"
        report(
            "fill",
            f"{step_label}: {info['filled'] - before_fill} fields",
            info["filled"] > before_fill,
        )

        leftover = await _workday_errors(page)
        info["unknown_required"] = leftover
        if await _submit_visible(page):
            return await finish_application(page, page, profile, auto_submit, job_id, info, LOG_DIR)

        before = await _step_name(page)
        moved = await _click_next(page)
        await _wait_ready(page, 1100)
        if not moved:
            if await captcha_present(page):
                report("error", "CAPTCHA blocked the wizard", False)
                await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
                return _result("needs_review", "CAPTCHA present — complete this one in the browser", info)
            return await finish_application(page, page, profile, auto_submit, job_id, info, LOG_DIR)
        after = await _step_name(page)
        report("next", after or f"step {step + 2}", True)
        if before and after and before == after:
            return await finish_application(page, page, profile, auto_submit, job_id, info, LOG_DIR)
        logger.info(f"Workday next page ({step + 1}) for {job_title}")

    await screenshot_failure(page, LOG_DIR / f"{job_id}.png")
    return _result("needs_review", "Workday wizard exceeded step limit", info)

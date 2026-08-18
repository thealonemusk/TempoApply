"""Generic Playwright form filling: discover fields, map labels, type values, upload resume."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import FrameLocator, Page, TimeoutError as PlaywrightTimeout

from backend.applier.fields import (
    is_consent_label,
    is_skip_field,
    pick_option,
    resolve_value,
)
from backend.applier.profile import ApplicantProfile


def apply_result(status: str, message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {"status": status, "message": message}
    if extra:
        out.update(extra)
    return out


COOKIE_NAMES = (
    "Accept all", "Accept All", "Accept cookies", "Accept Cookies",
    "I agree", "Agree", "Got it", "Allow all", "Allow All", "OK", "Okay",
)
APPLY_NAMES = (
    "Apply for this job", "Apply Now", "Apply Manually", "Start application",
    "I'm interested", "Submit application", "Apply",
)
SKIP_APPLY_SUBSTRINGS = (
    "linkedin", "indeed", "google", "facebook", "continue with", "sign in with",
    "easy apply",
)
NEXT_NAMES = ("Next", "Continue", "Save and continue", "Save & Continue")
SUBMIT_NAMES = (
    "Submit application", "Submit Application", "Send application",
    "Submit my application", "Submit",
)

FIELD_JS = """() => {
  const visible = (el) => {
    if (!el) return false;
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const labelFor = (el) => {
    const aria = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    if (el.labels && el.labels.length) return el.labels[0].innerText;
    if (el.id) {
      const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lab) return lab.innerText;
    }
    const wrap = el.closest('label, fieldset, .field, .form-field, .application-question, [class*="question"], [data-automation-id*="formField"], [class*="FormField"]');
    if (wrap) {
      const lab = wrap.querySelector('label, legend, [class*="label"], [data-automation-id$="label"]');
      if (lab && lab !== el) return lab.innerText;
      const text = wrap.innerText || '';
      return text.split('\\n')[0].slice(0, 180);
    }
    return el.placeholder || el.name || el.getAttribute('data-automation-id') || '';
  };
  const selectorFor = (el, idx) => {
    const auto = el.getAttribute('data-automation-id');
    if (auto) return `[data-automation-id="${auto}"]`;
    if (el.id) return `#${CSS.escape(el.id)}`;
    const name = el.getAttribute('name');
    if (name) return `${el.tagName.toLowerCase()}[name="${name}"]`;
    return `[data-ta-idx="${idx}"]`;
  };
  const nodes = Array.from(document.querySelectorAll('input, textarea, select, [role="combobox"], [contenteditable="true"]'));
  nodes.forEach((el, idx) => el.setAttribute('data-ta-idx', String(idx)));
  const out = [];
  for (const el of nodes) {
    if (el.closest('.iti__country-list') || el.classList.contains('iti__search-input')) continue;
    const type = (el.getAttribute('type') || el.tagName || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) continue;
    if (!visible(el) && type !== 'file') continue;
    const idx = el.getAttribute('data-ta-idx');
    const options = el.tagName === 'SELECT'
      ? Array.from(el.options).map(o => o.text)
      : [];
    out.push({
      idx,
      selector: selectorFor(el, idx),
      tag: el.tagName.toLowerCase(),
      type,
      name: el.getAttribute('name') || '',
      id: el.id || '',
      autocomplete: el.getAttribute('autocomplete') || '',
      placeholder: el.getAttribute('placeholder') || '',
      automation: el.getAttribute('data-automation-id') || '',
      required: el.required || el.getAttribute('aria-required') === 'true',
      label: (labelFor(el) || '').trim(),
      value: (el.value || el.innerText || '').trim(),
      options,
      role: el.getAttribute('role') || '',
    });
  }
  return out;
}"""


async def _scope_eval(scope: Page | FrameLocator, expression: str):
    if isinstance(scope, Page):
        return await scope.evaluate(expression)
    return await scope.locator("body").evaluate(expression)


async def dismiss_overlays(page: Page) -> None:
    for sel in (
        '#onetrust-accept-btn-handler',
        'button#onetrust-accept-btn-handler',
        'button:has-text("Accept All Cookies")',
        'button:has-text("Accept Cookies")',
        'button:has-text("Accept All")',
        '[data-automation-id="legalNoticeAcceptButton"]',
        '[data-automation-id="wd-LegalNotice-acceptButton"]',
        'button[data-automation-id="cookieAcceptButton"]',
        'button[aria-label="Close"]',
        '[aria-label="close"]',
        ".osano-cm-accept-all",
    ):
        loc = page.locator(sel)
        try:
            if await loc.count() and await loc.first.is_visible():
                await loc.first.click(timeout=1500)
                await page.wait_for_timeout(300)
        except Exception:
            continue
    for name in COOKIE_NAMES:
        loc = page.get_by_role("button", name=name, exact=False)
        try:
            if await loc.count() and await loc.first.is_visible():
                await loc.first.click(timeout=1500)
                await page.wait_for_timeout(300)
        except Exception:
            continue
    for sel in ('button[aria-label="Close"]', '[aria-label="close"]', ".osano-cm-accept-all"):
        loc = page.locator(sel)
        try:
            if await loc.count() and await loc.first.is_visible():
                await loc.first.click(timeout=1200)
        except Exception:
            continue


async def application_frame(page: Page) -> Page | FrameLocator:
    for sel in ("#grnhse_iframe", "iframe[id*='grnhse']"):
        loc = page.locator(sel)
        try:
            if not await loc.count():
                continue
            frame = page.frame_locator(sel)
            if await frame.locator("input, textarea, select").count() > 0:
                return frame
        except Exception:
            continue
    return page


def _locator(scope: Page | FrameLocator, selector: str):
    return scope.locator(selector)


async def upload_resume(scope: Page | FrameLocator, resume: Path, page: Optional[Page] = None) -> bool:
    # Greenhouse-style Attach button opens a file chooser.
    host = page or (scope if isinstance(scope, Page) else None)
    if host is not None:
        attach = scope.get_by_role("button", name="Attach", exact=False)
        try:
            if await attach.count() and await attach.first.is_visible():
                async with host.expect_file_chooser(timeout=5000) as chooser_info:
                    await attach.first.click()
                chooser = await chooser_info.value
                await chooser.set_files(str(resume))
                logger.info("Uploaded resume via Attach file chooser")
                await asyncio.sleep(0.6)
                return True
        except Exception as exc:
            logger.debug(f"Attach chooser upload failed: {exc}")

    files = _locator(scope, 'input[type="file"]')
    try:
        count = await files.count()
    except Exception:
        return False
    if not count:
        return False
    for i in range(count):
        inp = files.nth(i)
        try:
            blob = ""
            try:
                blob = " ".join(
                    (await inp.get_attribute(attr, timeout=1500) or "")
                    for attr in ("name", "id", "aria-label")
                ).lower()
            except Exception:
                blob = ""
            if "cover" in blob:
                continue
            await inp.set_input_files(str(resume), timeout=8000)
            logger.info(f"Uploaded resume to file input {i}")
            await asyncio.sleep(0.4)
            return True
        except Exception as exc:
            logger.debug(f"Resume upload failed on input {i}: {exc}")
    return False


async def _fill_text(scope: Page | FrameLocator, selector: str, value: str) -> bool:
    loc = _locator(scope, selector).first
    try:
        if not await loc.count():
            return False
        await loc.click(timeout=2500)
        await loc.fill("")
        await loc.fill(value)
        return True
    except Exception:
        try:
            await loc.press_sequentially(value, delay=15)
            return True
        except Exception as exc:
            logger.debug(f"Text fill failed {selector}: {exc}")
            return False


async def _select_option(scope: Page | FrameLocator, selector: str, options: List[str], desired: str) -> bool:
    choice = pick_option(options, desired)
    if not choice:
        return False
    loc = _locator(scope, selector).first
    try:
        await loc.select_option(label=choice)
        return True
    except Exception:
        try:
            await loc.select_option(value=choice)
            return True
        except Exception:
            return False


async def _fill_combobox(scope: Page | FrameLocator, selector: str, value: str) -> bool:
    loc = _locator(scope, selector).first
    try:
        try:
            await loc.click(timeout=2000, force=True)
        except Exception:
            control = loc.locator('xpath=ancestor::*[contains(@class,"select")][1]')
            if await control.count():
                await control.first.click(timeout=2000, force=True)
            else:
                return False
        typed = False
        for inp_sel in (
            selector,
            f"{selector} input",
            "input.select__input",
            'input[id*="react-select"]',
        ):
            try:
                target = _locator(scope, inp_sel).last if inp_sel != selector else loc
                await target.fill(value, timeout=1200)
                typed = True
                break
            except Exception:
                continue
        if not typed:
            try:
                await loc.press_sequentially(value, delay=20)
            except Exception:
                pass
        await asyncio.sleep(0.35)
        menu = scope.locator('.select__option, [class*="select__option"], [role="option"]:not(.iti__country)')
        count = min(await menu.count(), 30)
        desired = (value or "").strip().lower()
        first_visible = None
        for i in range(count):
            el = menu.nth(i)
            try:
                if not await el.is_visible():
                    continue
            except Exception:
                continue
            if first_visible is None:
                first_visible = el
            text = ((await el.inner_text()) or "").strip().lower()
            if desired and (desired in text or text in desired):
                await el.click(timeout=2000, force=True)
                return True
        if first_visible is not None:
            await first_visible.click(timeout=2000, force=True)
            return True
        await loc.press("Enter")
        return True
    except Exception as exc:
        logger.debug(f"Combobox fill failed {selector}: {exc}")
        return False


async def _check_if_needed(scope: Page | FrameLocator, selector: str, label: str, desired: str) -> bool:
    loc = _locator(scope, selector).first
    try:
        if await loc.is_checked():
            return True
        want_yes = desired.lower() in {"yes", "true", "y", "1"} or is_consent_label(label)
        if want_yes:
            await loc.check()
            return True
        return False
    except Exception:
        return False


async def _choose_radio(scope: Page | FrameLocator, name: str, desired: str, options_hint: str = "") -> bool:
    if not name:
        return False
    radios = _locator(scope, f'input[type="radio"][name="{name}"]')
    try:
        count = await radios.count()
    except Exception:
        return False
    labels = []
    for i in range(count):
        r = radios.nth(i)
        rid = await r.get_attribute("id") or ""
        value = await r.get_attribute("value") or ""
        lab = ""
        if rid:
            lab_loc = _locator(scope, f'label[for="{rid}"]')
            if await lab_loc.count():
                lab = (await lab_loc.first.inner_text()).strip()
        labels.append(lab or value)
    choice = pick_option(labels, desired)
    if not choice:
        return False
    for i, lab in enumerate(labels):
        if lab == choice:
            try:
                await radios.nth(i).check()
                return True
            except Exception:
                try:
                    await radios.nth(i).click(force=True)
                    return True
                except Exception:
                    return False
    return False


async def collect_fields(scope: Page | FrameLocator) -> List[Dict[str, Any]]:
    try:
        if isinstance(scope, Page):
            return await scope.evaluate(FIELD_JS)
        return await scope.locator("body").evaluate(FIELD_JS)
    except Exception as exc:
        logger.debug(f"Field collection failed: {exc}")
        return []


async def fill_form(
    scope: Page | FrameLocator,
    profile: ApplicantProfile,
    job_title: str,
    company: str,
) -> Dict[str, Any]:
    """Fill every visible mapped field. Returns counts and leftover required labels."""
    fields = await collect_fields(scope)
    filled = 0
    skipped = 0
    unknown_required: List[str] = []
    seen_radio = set()

    for field in fields:
        label = field.get("label") or field.get("placeholder") or field.get("name") or ""
        ftype = field.get("type") or ""
        name = field.get("name") or ""
        selector = field.get("selector")
        if not selector:
            continue
        if is_skip_field(label, name, field.get("autocomplete") or ""):
            skipped += 1
            continue
        if ftype == "file":
            continue
        current = (field.get("value") or "").strip()
        if current and ftype not in {"checkbox", "radio"}:
            continue

        desired = resolve_value(profile, label, job_title, company)
        if ftype in {"tel", "phone"} or "phone" in (label + name).lower():
            if not desired:
                desired = profile.phone_e164() or profile.phone_national()
            elif desired.startswith("+") and "country" in label.lower():
                desired = profile.phone_country

        if ftype == "date" and desired and not desired[:1].isdigit():
            desired = profile.available_date_iso()

        if ftype == "checkbox":
            ok = await _check_if_needed(scope, selector, label, desired or ("Yes" if is_consent_label(label) else ""))
            if ok:
                filled += 1
            continue

        if ftype == "radio":
            if name in seen_radio:
                continue
            seen_radio.add(name)
            if not desired:
                if field.get("required"):
                    unknown_required.append(label)
                continue
            ok = await _choose_radio(scope, name, desired)
            if ok:
                filled += 1
            elif field.get("required"):
                unknown_required.append(label)
            continue

        if not desired:
            if field.get("required"):
                unknown_required.append(label)
            continue

        ok = False
        if field.get("tag") == "select" or ftype == "select-one":
            ok = await _select_option(scope, selector, field.get("options") or [], desired)
        elif field.get("role") == "combobox" or "combobox" in (field.get("automation") or "").lower():
            ok = await _fill_combobox(scope, selector, desired)
        else:
            ok = await _fill_text(scope, selector, desired)

        if ok:
            filled += 1
        elif field.get("required"):
            unknown_required.append(label)

    return {
        "filled": filled,
        "skipped": skipped,
        "unknown_required": [x for x in unknown_required if x],
        "field_count": len(fields),
    }


async def click_named_button(scope: Page | FrameLocator, names: tuple, timeout: int = 2500) -> bool:
    for name in names:
        for role in ("button", "link"):
            loc = scope.get_by_role(role, name=name, exact=False)
            try:
                count = await loc.count()
            except Exception:
                continue
            for i in range(count):
                target = loc.nth(i)
                try:
                    if not await target.is_visible():
                        continue
                    text = (await target.inner_text()).lower()
                    if any(s in text for s in SKIP_APPLY_SUBSTRINGS):
                        continue
                    await target.click(timeout=timeout)
                    return True
                except Exception:
                    continue
    return False


async def click_apply(page: Page) -> bool:
    await dismiss_overlays(page)
    if await click_named_button(page, APPLY_NAMES):
        await page.wait_for_timeout(800)
        return True
    loc = page.locator('[data-automation-id="adventureButton"], a[href*="/apply"], button[data-test="apply-button"]')
    try:
        if await loc.count() and await loc.first.is_visible():
            await loc.first.click(timeout=2500)
            await page.wait_for_timeout(800)
            return True
    except Exception:
        pass
    return False


async def click_next(scope: Page | FrameLocator) -> bool:
    wd = _locator(scope, '[data-automation-id="bottom-navigation-next-button"], [data-automation-id="pageFooterNextButton"]')
    try:
        if await wd.count() and await wd.first.is_visible():
            await wd.first.click(timeout=3000)
            return True
    except Exception:
        pass
    return await click_named_button(scope, NEXT_NAMES)


async def click_submit(scope: Page | FrameLocator) -> bool:
    wd = _locator(
        scope,
        '[data-automation-id="bottom-navigation-submit-button"], [data-automation-id="pageFooterSubmitButton"]',
    )
    try:
        if await wd.count() and await wd.first.is_visible():
            await wd.first.click(timeout=4000)
            return True
    except Exception:
        pass
    return await click_named_button(scope, SUBMIT_NAMES, timeout=4000)


async def unfilled_required(scope: Page | FrameLocator) -> List[str]:
    js = """() => {
      const vis = (el) => {
        const s = window.getComputedStyle(el);
        if (s.display === 'none' || s.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      };
      const out = [];
      const nodes = document.querySelectorAll('input, textarea, select');
      for (const el of nodes) {
        if (!el.required && el.getAttribute('aria-required') !== 'true') continue;
        if (!vis(el)) continue;
        const type = (el.type || '').toLowerCase();
        if (['hidden', 'submit', 'button'].includes(type)) continue;
        if (el.closest('[data-automation-id="multiSelectContainer"], [data-automation-id="selectedItemList"]')) {
          const wrap = el.closest('[data-automation-id^="formField-"]');
          if (wrap && /item selected/i.test(wrap.innerText || '')) continue;
        }
        let empty = false;
        if (type === 'checkbox' || type === 'radio') {
          const group = document.querySelectorAll(`[name="${el.name}"]`);
          empty = ![...group].some(g => g.checked);
        } else if (type === 'file') {
          empty = !el.files || el.files.length === 0;
        } else {
          empty = !(el.value || '').trim();
        }
        if (empty) {
          const label = (el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute('aria-label') || el.name || el.id;
          out.push((label || 'required field').trim());
        }
      }
      return [...new Set(out)];
    }"""
    try:
        if isinstance(scope, Page):
            return await scope.evaluate(js)
        return await scope.locator("body").evaluate(js)
    except Exception:
        return []


SUCCESS_TEXT = (
    "thank you for applying",
    "thanks for applying",
    "application submitted",
    "application has been submitted",
    "we've received your application",
    "we have received your application",
    "successfully applied",
    "application received",
    "you have applied",
    "successfully submitted",
    "your application was submitted",
    "we received your application",
)

SUCCESS_URL_PARTS = ("/confirmation", "/thanks", "/thank-you", "application-submitted", "applied=true")


async def application_succeeded(page: Page) -> bool:
    url = (page.url or "").lower()
    if any(part in url for part in SUCCESS_URL_PARTS):
        return True
    try:
        body = (await page.inner_text("body")).lower()
    except Exception:
        return False
    return any(s in body for s in SUCCESS_TEXT)


async def captcha_present(page: Page) -> bool:
    loc = page.locator("iframe[src*='recaptcha'], iframe[src*='hcaptcha'], .g-recaptcha")
    try:
        count = await loc.count()
    except Exception:
        return False
    for i in range(count):
        try:
            el = loc.nth(i)
            if not await el.is_visible():
                continue
            box = await el.bounding_box()
            if box and box.get("height", 0) >= 40 and box.get("width", 0) >= 40:
                return True
        except Exception:
            continue
    return False


async def screenshot_failure(page: Page, dest: Path) -> None:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(dest), full_page=True)
    except Exception as exc:
        logger.debug(f"Screenshot failed: {exc}")


async def wait_settled(page: Page, ms: int = 900) -> None:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeout:
        pass
    await page.wait_for_timeout(ms)


async def finish_application(
    page: Page,
    scope,
    profile: ApplicantProfile,
    auto_submit: bool,
    job_id: str,
    filled_info: Dict[str, Any],
    log_dir: Path,
) -> Dict[str, Any]:
    if await application_succeeded(page):
        return apply_result("applied", "Application submitted", filled_info)

    leftover = await unfilled_required(scope)
    leftover += filled_info.get("unknown_required") or []
    leftover = [x for x in leftover if x]
    filled = int(filled_info.get("filled") or 0)
    uploaded = bool(filled_info.get("resume_uploaded"))

    if filled == 0 and not uploaded:
        await screenshot_failure(page, log_dir / f"{job_id}.png")
        return apply_result("failed", "No application form was found or filled on this posting", filled_info)

    if leftover:
        await screenshot_failure(page, log_dir / f"{job_id}.png")
        return apply_result(
            "needs_review",
            "Required fields could not be filled: " + "; ".join(leftover[:8]),
            filled_info,
        )

    if not auto_submit or not profile.auto_submit:
        await screenshot_failure(page, log_dir / f"{job_id}-filled.png")
        return apply_result("needs_review", "Form filled. auto_submit is off — submit manually.", filled_info)

    if await captcha_present(page):
        await screenshot_failure(page, log_dir / f"{job_id}.png")
        return apply_result("needs_review", "CAPTCHA present — complete this one in the browser", filled_info)

    clicked = await click_submit(scope)
    await wait_settled(page, 1500)
    if await application_succeeded(page):
        return apply_result("applied", "Application submitted", filled_info)
    if clicked:
        await wait_settled(page, 2000)
        if await application_succeeded(page):
            return apply_result("applied", "Application submitted", filled_info)
        await screenshot_failure(page, log_dir / f"{job_id}.png")
        return apply_result(
            "needs_review",
            "Submit clicked but confirmation was not detected. Check the screenshot.",
            filled_info,
        )
    await screenshot_failure(page, log_dir / f"{job_id}.png")
    return apply_result("needs_review", "Could not find a submit button", filled_info)

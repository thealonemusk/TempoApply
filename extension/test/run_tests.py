"""
Tests for the autofill extension.

Default run (no flags) needs nothing but Playwright's chromium: it loads the
local harness, injects `scrape.js` and `fill.js`, resolves through the real
backend resolver in-process, and asserts on the resulting DOM.

`--integration` loads the actual unpacked extension into Chrome and drives the
widget, which is the only way to cover the service worker, chrome.runtime
messaging and the cross-frame fan-out that Glassdoor's embedded form needs. It
requires the API server to be running (`python run.py`).

    python extension/test/run_tests.py
    python extension/test/run_tests.py --integration
"""
from __future__ import annotations

import asyncio
import functools
import http.server
import socketserver
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXT = ROOT / "extension"
sys.path.insert(0, str(ROOT))

PORT = 8765
failures: list[str] = []


def check(name: str, got, want) -> None:
    ok = (want in got) if isinstance(want, str) and isinstance(got, str) and want else got == want
    if isinstance(want, str) and want.startswith("!"):
        ok = want[1:] != got
    print(f"  {'PASS' if ok else 'FAIL'}  {name:26} {str(got)[:52]!r}")
    if not ok:
        failures.append(f"{name}: expected {want!r}, got {got!r}")


# ── Unit: scraper + filler against the real resolver ─────────────────────────

async def run_unit() -> None:
    from fastapi.testclient import TestClient
    from playwright.async_api import async_playwright

    from backend.api.main import app

    client = TestClient(app)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        await page.goto((EXT / "test" / "harness.html").as_uri())
        for name in ("scrape.js", "fill.js"):
            await page.add_script_tag(path=str(EXT / "src" / name))

        fields = await page.evaluate("() => { window.__S = window.__TA.scrape(); return window.__S.fields; }")
        print(f"\nScraped {len(fields)} fields from the Workday/Glassdoor/Greenhouse harness")

        data = client.post(
            "/api/autofill/resolve",
            json={
                "url": "https://acme.wd5.myworkdayjobs.com/en-US/careers/job/Backend-Engineer_R-1/apply",
                "page_title": await page.title(),
                "fields": fields,
            },
        ).json()
        resume = client.get("/api/autofill/resume").json()

        await page.evaluate("() => window.__TA.injectStyles()")
        result = await page.evaluate(
            """async ([fills, resume]) => {
                 const file = window.__TA.base64ToFile(resume.b64, resume.filename, resume.mime);
                 const out = await window.__TA.applyFills(fills, window.__S.elements, file);
                 return { applied: out.applied.length, failed: out.failed.map(f => `${f.action}:${f.label}`) };
               }""",
            [data["fills"], resume],
        )
        print(f"Applied {result['applied']}, failed {len(result['failed'])} {result['failed']}")

        dom = await page.evaluate(
            """() => {
                 const v = (s) => { const e = document.querySelector(s); return e ? e.value : '<missing>'; };
                 const t = (s) => { const e = document.querySelector(s); return e ? e.textContent.trim() : '<missing>'; };
                 const f = (s) => { const e = document.querySelector(s); return e && e.files.length ? e.files[0].name : ''; };
                 const r = (n) => { const e = document.querySelector(`input[name="${n}"]:checked`); return e ? e.value : ''; };
                 return {
                   wd_first: v('#wd-first'), wd_city: v('#wd-city'), wd_phone: v('#wd-phone'),
                   wd_country: t('[data-automation-id="countryDropdown"]'),
                   wd_phone_type: t('[data-automation-id="phone-device-type"]'),
                   wd_source: t('[data-automation-id="multiSelectContainer"]'),
                   wd_sponsor: t('[data-automation-id="sponsorshipDropdown"]'),
                   wd_auth: t('[data-automation-id="workAuthDropdown"]'),
                   wd_resume: f('#wd-resume'),
                   gd_email: v('#gd-email'), gd_relocate: r('relocate'), gd_sponsor: r('sponsor'),
                   gh_school: v('#gh-school'), gh_degree: v('#gh-degree'), gh_gender: v('#gh-gender'),
                   gh_hear: t('.select__control'), gh_start: v('#gh-start'), gh_why: v('#gh-why'),
                   gh_resume: f('#gh-resume'), gh_cover: f('#gh-cover'),
                   gh_consent: document.querySelector('input[name="consent"]').checked,
                   honeypot: v('input[name="website_url"]'),
                 };
               }"""
        )

        print("\nWorkday — custom dropdowns, no <select> anywhere")
        check("first name", dom["wd_first"], "Ashutosh")
        check("city", dom["wd_city"], "Noida")
        check("phone", dom["wd_phone"], "+919939964663")
        check("country dropdown", dom["wd_country"], "India")
        check("phone device type", dom["wd_phone_type"], "Mobile")
        check("source multiselect", dom["wd_source"], "Company Website")
        check("sponsorship", dom["wd_sponsor"], "No")
        check("work authorization", dom["wd_auth"], "Yes")
        check("resume upload", dom["wd_resume"], "!")

        print("\nGlassdoor — fieldset/legend radio groups")
        check("email", dom["gd_email"], "@")
        check("relocate radio", dom["gd_relocate"], "yes")
        check("sponsorship radio", dom["gd_sponsor"], "no")

        print("\nGreenhouse — native selects and a react-select combobox")
        check("school select", dom["gh_school"], "National Institute")
        check("degree select", dom["gh_degree"], "B.Tech")
        check("gender select", dom["gh_gender"], "Decline")
        check("how-heard combobox", dom["gh_hear"], "Company website")
        check("date input is ISO", len(dom["gh_start"]), 10)
        check("consent checkbox", dom["gh_consent"], True)
        check("resume upload", dom["gh_resume"], "!")

        print("\nMust NOT be touched")
        check("spam trap stays empty", dom["honeypot"], "")
        check("cover-letter input", dom["gh_cover"], "")
        check("subjective question", dom["gh_why"], "")
        check("flagged for the human", "Why do you want to work here?" in " ".join(data["unresolved"]), True)

        if errors:
            failures.append(f"page errors: {errors[:3]}")
        await browser.close()


# ── Unit: Workday's repeating My Experience step ─────────────────────────────

async def run_sections() -> None:
    """Work Experience / Education / Websites start empty behind an Add button."""
    from fastapi.testclient import TestClient
    from playwright.async_api import async_playwright

    from backend.api.main import app

    client = TestClient(app)
    url = "https://acme.wd5.myworkdayjobs.com/en-US/careers/job/Backend-Engineer_R-1/apply"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        await page.goto((EXT / "test" / "harness-experience.html").as_uri())
        for name in ("scrape.js", "fill.js"):
            await page.add_script_tag(path=str(EXT / "src" / name))

        before = await page.evaluate("() => window.__TA.scrape().fields.length")
        first = client.post(
            "/api/autofill/resolve",
            json={"url": url, "page_title": "My Experience",
                  "fields": await page.evaluate("() => window.__TA.scrape().fields")},
        ).json()

        added = await page.evaluate("async (n) => window.__TA.expandSections(n)", first["sections_needed"])
        fields = await page.evaluate("() => { window.__S = window.__TA.scrape(); return window.__S.fields; }")

        data = client.post(
            "/api/autofill/resolve",
            json={"url": url, "page_title": "My Experience", "fields": fields},
        ).json()
        resume = client.get("/api/autofill/resume").json()
        await page.evaluate("() => window.__TA.injectStyles()")
        out = await page.evaluate(
            """async ([fills, resume]) => {
                 const file = window.__TA.base64ToFile(resume.b64, resume.filename, resume.mime);
                 const r = await window.__TA.applyFills(fills, window.__S.elements, file);
                 return { applied: r.applied.length, failed: r.failed.map(f => `${f.action}:${f.label}`) };
               }""",
            [data["fills"], resume],
        )

        dom = await page.evaluate(
            """() => {
                 const at = (auto, sel) => {
                   const p = document.querySelector(`[data-automation-id="${auto}"]`);
                   if (!p) return '<no entry>';
                   const e = p.querySelector(sel);
                   return e ? (e.value ?? e.textContent.trim()) : '<missing>';
                 };
                 const checked = (auto, sel) => {
                   const p = document.querySelector(`[data-automation-id="${auto}"]`);
                   const e = p && p.querySelector(sel);
                   return e ? e.checked : false;
                 };
                 return {
                   e1_title: at('workExperience-1','[data-automation-id="jobTitle"]'),
                   e1_company: at('workExperience-1','[data-automation-id="company"]'),
                   e1_desc: at('workExperience-1','[data-automation-id="description"]'),
                   e1_current: checked('workExperience-1','[data-automation-id="currentlyWorkHere"]'),
                   e2_title: at('workExperience-2','[data-automation-id="jobTitle"]'),
                   e2_company: at('workExperience-2','[data-automation-id="company"]'),
                   school: at('education-1','[data-automation-id="school"]'),
                   degree: at('education-1','[data-automation-id="multiSelectContainer"]'),
                   field: at('education-1','[data-automation-id="fieldOfStudy"]'),
                   gpa: at('education-1','[data-automation-id="gpa"]'),
                   w1: at('websitePanelSet-1','[data-automation-id="website"]'),
                   w3: at('websitePanelSet-3','[data-automation-id="website"]'),
                   skills: document.querySelectorAll('[data-chips] .chip').length,
                 };
               }"""
        )

        print(
            f"\nWorkday My Experience — {before} fields before, {added} entries opened, "
            f"{len(fields)} after; applied {out['applied']}, failed {out['failed']}"
        )
        check("nothing to fill at first", before <= 2, True)
        check("opened every entry", added, 6)
        check("entry 1 job title", dom["e1_title"], "Software Engineer")
        check("entry 1 company", dom["e1_company"], "Paytm")
        check("entry 1 description", dom["e1_desc"], "Indonesia IoT")
        check("entry 1 currently here", dom["e1_current"], True)
        check("entry 2 is the 2nd job", dom["e2_title"], "Software Developer Intern")
        check("entry 2 company", dom["e2_company"], "Denr")
        check("education school", dom["school"], "National Institute")
        check("education degree", dom["degree"], "B.Tech")
        check("education field", dom["field"], "Computer Science")
        check("education gpa", dom["gpa"], "7.79")
        check("website 1 = linkedin", dom["w1"], "linkedin.com")
        check("website 3 = portfolio", dom["w3"], "is-a.dev")
        check("skills picked one by one", dom["skills"] >= 5, True)
        check("no field refused", len(out["failed"]), 0)

        if errors:
            failures.append(f"page errors: {errors[:3]}")
        await browser.close()


# ── Repeating entries with unrecognisable container ids ──────────────────────

UNKNOWN_IDS_HTML = """
<h3>Work Experience</h3>
<div data-automation-id="panelSet-abc-1">
  <label for="t1">Job Title</label><input id="t1">
  <label for="c1">Company</label><input id="c1">
  <label for="d1">Role Description</label><textarea id="d1"></textarea>
</div>
<div data-automation-id="panelSet-abc-2">
  <label for="t2">Job Title</label><input id="t2">
  <label for="c2">Company</label><input id="c2">
  <label for="d2">Role Description</label><textarea id="d2"></textarea>
</div>
<h3>Websites</h3>
<div data-automation-id="panelSet-xyz-1"><label for="u1">URL</label><input id="u1"></div>
<div data-automation-id="panelSet-xyz-2"><label for="u2">URL</label><input id="u2"></div>
"""


async def run_unknown_containers() -> None:
    """
    The real failure: a tenant whose entry containers are not named
    workExperience-1. Untagged fields fall through to the flat resolver, which
    has no alias for a bare "Company" or "Role Description", so they stay empty.
    Entry membership has to be recoverable from repetition order alone.
    """
    from fastapi.testclient import TestClient
    from playwright.async_api import async_playwright

    from backend.api.main import app

    client = TestClient(app)
    print("\nRepeating entries when the container ids are unknown")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(UNKNOWN_IDS_HTML)
        await page.add_script_tag(path=str(EXT / "src" / "scrape.js"))
        fields = await page.evaluate("() => window.__TA.scrape().fields")

        def tagged(label, index):
            return next(
                (f for f in fields
                 if f["label"].strip().lower() == label.lower()
                 and f.get("section_index") == index),
                None,
            )

        check("first Company is entry 1", bool(tagged("Company", 1)), True)
        check("second Company is entry 2", bool(tagged("Company", 2)), True)
        check("first Role Description is entry 1", bool(tagged("Role Description", 1)), True)
        check("second Role Description is entry 2", bool(tagged("Role Description", 2)), True)
        check("Company tagged as experience",
              (tagged("Company", 1) or {}).get("section_kind"), "experience")
        check("URL tagged as website", (tagged("URL", 1) or {}).get("section_kind"), "website")
        check("second URL is entry 2", bool(tagged("URL", 2)), True)

        data = client.post("/api/autofill/resolve", json={
            "url": "https://acme.wd5.myworkdayjobs.com/x/apply",
            "page_title": "My Experience", "fields": fields,
        }).json()
        values = {f["label"]: f["value"] for f in data["fills"] if f["action"] != "skip"}
        filled = [f for f in data["fills"] if f["action"] != "skip"]

        # 2 entries x (Job Title, Company, Role Description) + 2 URLs
        check("every field resolved", len(filled), 8)
        by_idx = {}
        for f in data["fills"]:
            if f["action"] != "skip" and f["key"]:
                by_idx[f["key"]] = by_idx.get(f["key"], 0) + 1
        check("employer 1 is Paytm",
              any(f["value"] == "Paytm" for f in filled), True)
        check("employer 2 is the internship",
              any("Denr" in f["value"] for f in filled), True)
        check("websites are three different links",
              len({f["value"] for f in filled if f["value"].startswith("http")}), 2)

        await browser.close()


# ── Integration: the real extension in Chrome ────────────────────────────────

def _serve(directory: Path):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


async def run_integration() -> None:
    import urllib.error
    import urllib.request

    from playwright.async_api import async_playwright

    try:
        urllib.request.urlopen("http://localhost:8000/api/autofill/ping", timeout=3).read()
    except (urllib.error.URLError, OSError) as exc:
        print(f"\nSKIP integration: backend not reachable ({exc}). Start it with `python run.py`.")
        return

    httpd = _serve(EXT / "test")
    profile = Path(tempfile.mkdtemp(prefix="ta-chrome-"))

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=False,
            args=[
                f"--disable-extensions-except={EXT}",
                f"--load-extension={EXT}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(f"http://127.0.0.1:{PORT}/harness-iframe.html")
            await page.wait_for_timeout(3000)

            print("\nIntegration — real extension, form inside an iframe")
            check("service worker running", len(ctx.service_workers), 1)
            check("widget mounted from iframe", await page.locator("#tempoapply-widget-host").count(), 1)

            panel = page.locator("#tempoapply-widget-host").locator("css=.panel")
            check("backend connected", await panel.locator("[data-dot]").get_attribute("class"), "up")

            await panel.locator("[data-fill]").click()
            await page.wait_for_timeout(6000)

            n_ok = await panel.locator("[data-n-ok]").inner_text()
            n_low = await panel.locator("[data-n-low]").inner_text()
            n_todo = await panel.locator("[data-n-todo]").inner_text()
            msg = (await panel.locator("[data-msg]").inner_text()) if await panel.locator("[data-msg]").is_visible() else ""
            print(f"    panel counters: filled={n_ok} check={n_low} you={n_todo} msg={msg!r}")
            check("fields reported filled", int(n_ok) >= 7, True)
            check("top frame filled", await page.locator("#top-email").input_value(), "@")

            frame = page.frames[1]
            check("iframe first name", await frame.locator("#f").input_value(), "Ashutosh")
            check("iframe phone", await frame.locator("#p").input_value(), "+91")
            check(
                "iframe radio group",
                await frame.evaluate(
                    "() => { const e = document.querySelector('input[name=\"auth\"]:checked'); return e ? e.value : ''; }"
                ),
                "yes",
            )
            check(
                "iframe resume upload",
                await frame.evaluate("() => document.querySelector('#r').files.length"),
                1,
            )
        finally:
            await ctx.close()
            httpd.shutdown()


async def main() -> None:
    await run_unit()
    await run_sections()
    await run_unknown_containers()
    if "--integration" in sys.argv:
        await run_integration()

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S):")
        for line in failures:
            print(f"  - {line}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

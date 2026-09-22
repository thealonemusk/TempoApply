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
        # National, not E.164: the form has its own country-code control, and
        # a "+91" typed into the number box on top of that is either rejected
        # by validation or submitted as +91+91.
        check("phone has no country code", dom["wd_phone"], "9939964663")
        check("phone country code is separate", dom["wd_phone"].startswith("+"), False)
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


async def run_tenant_variations() -> None:
    """
    Answers that differ per Workday tenant, all reported from live forms.

    No browser needed — these are resolver decisions, and every one of them
    silently left a required field blank rather than erroring.
    """
    from fastapi.testclient import TestClient

    from backend.api.main import app

    client = TestClient(app)
    print("\nTenant variations — device type, phone format, named links, split dates")

    def resolve(fields, url="https://acme.wd5.myworkdayjobs.com/x/apply"):
        data = client.post("/api/autofill/resolve", json={
            "url": url, "page_title": "Application", "fields": fields,
        }).json()
        return {f["idx"]: f for f in data["fills"]}

    def field(idx, label, **kw):
        base = {"idx": idx, "label": label, "tag": "input", "type": "text"}
        base.update(kw)
        return base

    # Phone Device Type: the taxonomy is per tenant. "Mobile" is preferred
    # where it exists; a tenant offering only Phone/Main must still answer.
    out = resolve([
        field("1", "Phone Device Type", tag="select", options=["Select", "Home", "Mobile", "Pager"]),
        field("2", "Phone Device Type", tag="select", options=["Select", "Phone", "Main", "Fax"]),
        field("3", "Phone Device Type", tag="button", role="combobox"),
    ])
    check("device type prefers Mobile", out["1"]["value"], "Mobile")
    check("device type falls back to Phone", out["2"]["value"], "Phone")
    check("device type not skipped", out["2"]["action"], "select")
    check("listbox gets the fallback list", "Main" in out["3"]["values"], True)
    check("listbox tries Mobile first", out["3"]["values"][0], "Mobile")

    # Phone number: the country code lives in its own control.
    out = resolve([
        field("1", "Phone Number", type="tel"),
        field("2", "Country Phone Code", tag="button", role="combobox"),
    ])
    check("phone number is national", out["1"]["value"], "9939964663")
    check("phone number has no +", out["1"]["value"].startswith("+"), False)
    check("country code is separate", out["2"]["value"], "+91")

    # A link box that names the network it wants is answered by name, not by
    # the position of its panel.
    out = resolve([
        field("1", "Please provide your LinkedIn profile",
              section_kind="website", section_index=2),
        field("2", "URL", section_kind="website", section_index=2),
        field("3", "Social Network URLs"),
    ])
    check("named LinkedIn box gets LinkedIn", "linkedin.com" in out["1"]["value"], True)
    check("unnamed panel 2 still positional", "github.com" in out["2"]["value"], True)
    check("Social Network URLs resolves", "linkedin.com" in out["3"]["value"], True)

    # Split date boxes. Workday labels them "Month"/"Year"; the scraper
    # qualifies them with their From/To group, and a current job leaves To blank.
    out = resolve([
        field("1", "From Month", section_kind="experience", section_index=1),
        field("2", "From Year", section_kind="experience", section_index=1),
        field("3", "To Month", section_kind="experience", section_index=1),
        field("4", "I currently work here", tag="input", type="checkbox",
              section_kind="experience", section_index=1),
        field("5", "To Month", section_kind="experience", section_index=2),
        field("6", "I currently work here", tag="input", type="checkbox",
              section_kind="experience", section_index=2),
    ])
    check("Paytm starts 01", out["1"]["value"], "01")
    check("Paytm starts 2025", out["2"]["value"], "2025")
    check("current job leaves To blank", out["3"]["action"], "skip")
    check("Paytm is ticked current", out["4"]["action"], "checkbox")
    check("past job keeps its end month", out["5"]["value"], "06")
    check("internship is NOT ticked current", out["6"]["action"], "skip")


ENTER_SKILLS_HTML = """
<!doctype html><meta charset="utf-8"><body>
  <div id="blockA">
    <label for="fn">First Name</label><input id="fn">
    <label for="ln">Last Name</label><input id="ln">
  </div>
  <div id="blockB">
    <label for="em">Email</label><input id="em">
    <label for="ph">Phone Number</label><input id="ph" type="tel">
  </div>
  <div data-automation-id="formField-skills">
    <label id="sk-label">Skills</label>
    <div data-automation-id="multiSelectContainer">
      <span class="chips"></span>
      <input id="sk" role="combobox" data-automation-id="searchBox" aria-labelledby="sk-label">
    </div>
  </div>
  <script>
    // A tag input with no listbox whatsoever: the only way in is type + Enter,
    // which is exactly how the failing Workday tenant behaves.
    var inp = document.getElementById('sk');
    inp.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      var v = inp.value.trim();
      if (!v) return;
      var chip = document.createElement('span');
      chip.setAttribute('data-automation-id', 'selectedItem');
      chip.textContent = v;
      document.querySelector('.chips').appendChild(chip);
      inp.value = '';
    });
  </script>
</body>
"""


async def run_enter_commit_and_sections() -> None:
    """
    Two things the Workday skills picker forced.

    A picker with no listbox has to be driven by Enter, and a long form has to
    be fillable one block at a time.
    """
    from playwright.async_api import async_playwright

    print("\nEnter-commit pickers and section-scoped scraping")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(ENTER_SKILLS_HTML)
        await page.add_script_tag(path=str(EXT / "src" / "scrape.js"))
        await page.add_script_tag(path=str(EXT / "src" / "fill.js"))

        # Section scoping: the same page, three different answers.
        counts = await page.evaluate(
            """() => ({
                 all: window.__TA.scrape().fields.length,
                 a: window.__TA.scrape(document.querySelector('#blockA')).fields.length,
                 b: window.__TA.scrape(document.querySelector('#blockB')).fields.length,
                 bLabels: window.__TA.scrape(document.querySelector('#blockB'))
                            .fields.map(f => f.label),
               })"""
        )
        check("whole page sees every field", counts["all"] >= 5, True)
        check("section A is just its two", counts["a"], 2)
        check("section B is just its two", counts["b"], 2)
        check("section B holds Email", any("Email" in l for l in counts["bLabels"]), True)
        check("section B excludes First Name",
              any("First Name" in l for l in counts["bLabels"]), False)

        # Enter-commit: no listbox exists, so only a keypress can land a value.
        committed = await page.evaluate(
            """async () => {
                 const { fields, elements } = window.__TA.scrape();
                 const skill = fields.find(f => (f.label || '').toLowerCase().includes('skill'));
                 const res = await window.__TA.applyFills(
                   [{ idx: skill.idx, action: 'multiselect', value: 'Java',
                      values: ['Java', 'Python', 'Docker'], label: 'Skills', confidence: 'low' }],
                   elements, null);
                 return {
                   chips: Array.from(document.querySelectorAll('[data-automation-id="selectedItem"]'))
                            .map(c => c.textContent),
                   applied: res.applied.length,
                   failed: res.failed.length,
                   leftover: document.getElementById('sk').value,
                 };
               }"""
        )
        check("every skill committed", committed["chips"], ["Java", "Python", "Docker"])
        check("picker reported success", committed["applied"], 1)
        check("nothing failed", committed["failed"], 0)
        check("search box left clean", committed["leftover"], "")

        await browser.close()


# A picker whose options come from a server, which is what Workday's Skills and
# Degree prompts really are. The menu never goes blank between values: it holds
# the PREVIOUS query's rows until the new ones arrive. Deciding on the first
# non-empty render therefore reads a stale list and answers "no match" — the
# failure that looks like "manually searching and clicking works, the extension
# does not".
ASYNC_PROMPT_HTML = """
<!doctype html><meta charset="utf-8"><body>
  <div data-automation-id="formField-skills">
    <label id="sk-label">Skills</label>
    <div data-automation-id="multiSelectContainer">
      <span class="chips"></span>
      <input id="sk" role="combobox" data-automation-id="searchBox" aria-labelledby="sk-label">
    </div>
  </div>
  <div id="menu"></div>
  <script>
    var TAXONOMY = {
      java: ['Java', 'JavaScript', 'Java EE'],
      python: ['Python', 'Python 3'],
      sql: ['SQL', 'SQL Server']
    };
    var inp = document.getElementById('sk');
    var menu = document.getElementById('menu');
    var timer = null;
    window.__latency = 500;

    function render(rows) {
      menu.innerHTML = '';
      rows.forEach(function (text) {
        var row = document.createElement('div');
        row.setAttribute('data-automation-id', 'promptOption');
        row.textContent = text;
        row.addEventListener('click', function () {
          var chip = document.createElement('span');
          chip.setAttribute('data-automation-id', 'selectedItem');
          chip.textContent = text;
          document.querySelector('.chips').appendChild(chip);
          inp.value = '';
          // The menu keeps the rows it was showing, exactly as Workday does.
        });
        menu.appendChild(row);
      });
    }

    inp.addEventListener('input', function () {
      var q = inp.value.trim().toLowerCase();
      if (timer) clearTimeout(timer);
      if (!q) return;
      // Nothing changes on screen yet: the old rows stay put while the
      // request is in flight.
      timer = setTimeout(function () {
        render(TAXONOMY[q] || ['No matching results']);
      }, window.__latency);
    });

    // Enter commits nothing here: a taxonomy prompt only accepts its own rows.
  </script>
</body>
"""


async def run_async_prompt() -> None:
    """
    A server-backed picker must be given time to answer.

    The menu holds the previous value's rows while the new ones are fetched, so
    a picker that decides on the first non-empty render picks nothing from the
    second value onwards.
    """
    from playwright.async_api import async_playwright

    print("\nServer-backed prompt (stale rows before the real answer)")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.set_content(ASYNC_PROMPT_HTML)
        await page.add_script_tag(path=str(EXT / "src" / "scrape.js"))
        await page.add_script_tag(path=str(EXT / "src" / "fill.js"))

        out = await page.evaluate(
            """async () => {
                 const started = Date.now();
                 const { fields, elements } = window.__TA.scrape();
                 const skill = fields.find(f => (f.label || '').toLowerCase().includes('skill'));
                 const res = await window.__TA.applyFills(
                   [{ idx: skill.idx, action: 'multiselect', value: 'Java',
                      values: ['Java', 'Python', 'SQL'], label: 'Skills', confidence: 'low' }],
                   elements, null);
                 return {
                   chips: Array.from(document.querySelectorAll('[data-automation-id="selectedItem"]'))
                            .map(c => c.textContent),
                   applied: res.applied.length,
                   leftover: document.getElementById('sk').value,
                   ms: Date.now() - started,
                 };
               }"""
        )
        # The second and third values are the ones that regress: the first is
        # typed into an empty menu, so even the old code waited for it.
        check("every skill committed", out["chips"], ["Java", "Python", "SQL"])
        check("picker reported success", out["applied"], 1)
        check("search box left clean", out["leftover"], "")
        check("no page errors", errors, [])

        # A value the taxonomy does not hold must not hang on the deadline, and
        # must not click the "No matching results" row.
        miss = await page.evaluate(
            """async () => {
                 document.querySelector('.chips').innerHTML = '';
                 const started = Date.now();
                 const { fields, elements } = window.__TA.scrape();
                 const skill = fields.find(f => (f.label || '').toLowerCase().includes('skill'));
                 const res = await window.__TA.applyFills(
                   [{ idx: skill.idx, action: 'multiselect', value: 'Cobol',
                      values: ['Cobol'], label: 'Skills', confidence: 'low' }],
                   elements, null);
                 return {
                   chips: document.querySelectorAll('[data-automation-id="selectedItem"]').length,
                   failed: res.failed.length,
                   ms: Date.now() - started,
                 };
               }"""
        )
        check("unknown skill committed nothing", miss["chips"], 0)
        check("unknown skill reported failure", miss["failed"], 1)
        check("a miss does not run out the clock", miss["ms"] < 4000, True)

        await browser.close()


# Workday as it actually behaves, which no other fixture here models:
#
#   * the Skills picker is React controlled — typing into its input changes
#     nothing, the value is only accepted through React's own onKeyDown prop;
#   * its menu is a popup at body level, tied back by data-associated-widget,
#     with a second widget's popup open at the same time to prove the tie is
#     used;
#   * a date is two spinbuttons that only commit on ArrowUp;
#   * a checkbox reports through aria-checked, a tick after the click.
#
# Shapes and mechanisms from job_app_filler by Berel Levy (BSD-3-Clause).
WORKDAY_REACT_HTML = """
<!doctype html><meta charset="utf-8"><body>
  <div data-automation-id="formField-skills">
    <label id="sk-label">Skills</label>
    <div id="skillsWidget" data-automation-id="multiSelectContainer"
         role="combobox" aria-labelledby="sk-label">
      <ul data-automation-id="selectedItemList"></ul>
      <input id="sk">
    </div>
  </div>

  <div data-automation-id="formField-startDate">
    <label id="from-label">From</label>
    <div data-automation-id="dateWidget" aria-labelledby="from-label">
      <input aria-label="Month" data-automation-id="dateSectionMonth-input" data-committed="">
      <input aria-label="Year" data-automation-id="dateSectionYear-input" data-committed="">
    </div>
  </div>

  <div data-automation-id="formField-currentlyWorkHere">
    <input id="cwh" type="checkbox" aria-checked="false">
    <label for="cwh">I currently work here</label>
  </div>

  <script>
    var TAXONOMY = { python: 'Python', sql: 'SQL' };
    var AMBIGUOUS = { java: ['Java', 'JavaScript', 'Java EE'] };
    var list = document.querySelector('[data-automation-id="selectedItemList"]');

    function commit(text) {
      var li = document.createElement('li');
      li.textContent = text;
      list.appendChild(li);
      killPopups();
    }
    function killPopups() {
      var old = document.querySelectorAll('[data-automation-widget="wd-popup"]');
      for (var i = 0; i < old.length; i++) old[i].remove();
    }
    function openPopup(rows, owner) {
      var pop = document.createElement('div');
      pop.setAttribute('data-automation-widget', 'wd-popup');
      pop.setAttribute('data-associated-widget', owner);
      rows.forEach(function (text) {
        var row = document.createElement('div');
        row.setAttribute('data-automation-id', 'promptOption');
        row.textContent = text;
        row.addEventListener('click', function () { commit(text); });
        pop.appendChild(row);
      });
      document.body.appendChild(pop);
    }

    // A decoy: another control's menu, open at the same time, offering a row
    // with the same text. Picking from this one would be the page-wide scan.
    openPopup(['Java'], 'someOtherWidget');
    document.querySelector('[data-associated-widget="someOtherWidget"]')
            .firstChild.addEventListener('click', function () {
              window.__pickedWrongPopup = true;
            });

    // React's props, exactly where React puts them.
    var input = document.getElementById('sk');
    input['__reactProps$tempoapply'] = {
      onKeyDown: function (e) {
        if (!e || e.key !== 'Tab') return;
        var v = ((e.target && e.target.value) || '').trim();
        var k = v.toLowerCase();
        if (TAXONOMY[k]) { commit(TAXONOMY[k]); return; }
        if (AMBIGUOUS[k]) {
          // The search runs on the server: the rows land well after the
          // keystroke. This is the "it just searches and never selects" case.
          setTimeout(function () { openPopup(AMBIGUOUS[k], 'skillsWidget'); }, 700);
          return;
        }
        // Unknown: nothing commits and no menu opens.
      }
    };
    // Typing does nothing at all, which is the point.
    input.addEventListener('input', function () { window.__typedAt = Date.now(); });

    // Spinbuttons: only ArrowUp moves committed state.
    document.querySelectorAll('[data-automation-id^="dateSection"]').forEach(function (el) {
      el.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowUp') return;
        var next = parseInt(el.value || '0', 10) + 1;
        el.value = String(next);
        el.setAttribute('data-committed', String(next));
      });
    });

    // React-controlled checkbox: the click is owned, state lands a tick later.
    var cb = document.getElementById('cwh');
    cb.addEventListener('click', function (e) {
      e.preventDefault();
      setTimeout(function () {
        cb.setAttribute('aria-checked', 'true');
        cb.checked = true;
      }, 250);
    });
  </script>
</body>
"""


async def run_workday_react_widgets() -> None:
    """
    The real Workday widgets: React-controlled prompt, portal menu, spinbutton
    dates, a checkbox that answers late.
    """
    from playwright.async_api import async_playwright

    print("\nWorkday React widgets (prompt portal, spinbuttons, late checkbox)")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.set_content(WORKDAY_REACT_HTML)
        await page.add_script_tag(path=str(EXT / "src" / "scrape.js"))
        await page.add_script_tag(path=str(EXT / "src" / "fill.js"))

        out = await page.evaluate(
            """async () => {
                 const { fields, elements } = window.__TA.scrape();
                 const find = (needle) => fields.find(
                   f => (f.label || '').toLowerCase().includes(needle));
                 const skills = find('skill');
                 const month = fields.find(f => /month/i.test(f.label || ''));
                 const year = fields.find(f => /year/i.test(f.label || ''));
                 const here = find('currently work');
                 const res = await window.__TA.applyFills([
                   { idx: skills.idx, action: 'multiselect', value: 'Java',
                     values: ['Java', 'Python'], label: 'Skills' },
                   { idx: month.idx, action: 'text', value: '01', label: 'From Month' },
                   { idx: year.idx, action: 'text', value: '2025', label: 'From Year' },
                   { idx: here.idx, action: 'checkbox', value: 'Yes',
                     label: 'I currently work here' },
                 ], elements, null);
                 const cb = document.getElementById('cwh');
                 const part = (sel) => document.querySelector(sel).getAttribute('data-committed');
                 return {
                   chips: Array.from(document.querySelectorAll(
                            '[data-automation-id="selectedItemList"] > li')).map(li => li.textContent),
                   wrongPopup: !!window.__pickedWrongPopup,
                   month: part('[data-automation-id="dateSectionMonth-input"]'),
                   year: part('[data-automation-id="dateSectionYear-input"]'),
                   checked: cb.getAttribute('aria-checked'),
                   applied: res.applied.length,
                   failed: res.failed.map(f => f.label),
                 };
               }"""
        )

        # Java is ambiguous, so it has to come off this widget's own popup;
        # Python commits straight through React.
        check("both skills committed", out["chips"], ["Java", "Python"])
        check("did not pick from another widget's menu", out["wrongPopup"], False)
        check("month committed via spinbutton", out["month"], "1")
        check("year committed via spinbutton", out["year"], "2025")
        check("checkbox waited for aria-checked", out["checked"], "true")
        check("everything applied", out["applied"], 4)
        check("nothing failed", out["failed"], [])
        check("no page errors", errors, [])

        await browser.close()


async def run_legal_questions() -> None:
    """
    Work authorization, sponsorship and the other yes/no legal questions.

    Checked twice: once normally, and once with `custom_answers` emptied. The
    second pass is the point — several of these only ever resolved because a
    custom answer happened to cover them, so a profile edit would have
    silently turned them back into blanks or, worse, into an address.
    """
    from backend.applier.fields import resolve_value
    from backend.applier.profile import load_profile

    profile = load_profile()
    bare = load_profile()
    bare.custom_answers = {}

    print("\nLegal questions — must hold without custom_answers")
    cases = [
        ("Are you legally authorized to work in the listed work location?", "Yes"),
        ("Are you legally authorised to work in the country of the job location?", "Yes"),
        ("Do you have the legal right to work in the listed location?", "Yes"),
        ("Will you now or in future require a sponsorship?", "No"),
        ("Will you require company sponsorship now or at any time in the future?", "No"),
        ("Do you now or will you in the future require immigration sponsorship?", "No"),
        ("Have you ever been employed by this company?", "No"),
        ("Are you a current or former employee of the company?", "No"),
        ("Are you subject to any employment agreements with your current employer?", "No"),
        ("Do you require any accommodation during the interview process?", "No"),
        ("What are your total years of professional experience?", "2"),
    ]
    for label, want in cases:
        check(label[:26], resolve_value(bare, label), want)

    # The precedence bug: a noun alias inside a yes/no question used to win.
    check("legal question is not an address",
          "Noida" in resolve_value(bare, "Do you have the legal right to work in the listed location?"),
          False)
    check("agreements question is not an employer",
          resolve_value(bare, "Are you subject to any employment agreements with your current employer?"),
          "No")

    # ...but a question-shaped label with no rule still falls back to the field,
    # and a plain field label is untouched by any of this.
    check("preferred work location", resolve_value(profile, "What is your preferred work location?"), "Noida")
    check("current company", resolve_value(profile, "Current Company"), "Paytm")
    check("email", resolve_value(profile, "Email Address"), "@")
    check("expected ctc", resolve_value(profile, "Expected CTC"), "2100000")
    check("linkedin", resolve_value(profile, "LinkedIn Profile"), "linkedin.com")


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
            check("iframe phone", await frame.locator("#p").input_value(), "9939964663")
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
    await run_tenant_variations()
    await run_legal_questions()
    await run_enter_commit_and_sections()
    await run_async_prompt()
    await run_workday_react_widgets()
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

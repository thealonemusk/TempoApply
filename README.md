# TempoApply — Entry-Level Job Search Engine

Automated multi-platform job discovery for early-career software roles. Scrapes LinkedIn, Indeed, Naukri, InstaHyre, and company career sites (Greenhouse, Lever, Workday), with hard filters for experience and senior titles.

## Quick start

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend

```bash
pip install -r backend/requirements.txt
python -m playwright install chromium
python run.py
```

API: `http://localhost:8000`

### Dashboard

```bash
cd dashboard
npm install
npm run dev
```

UI: `http://localhost:3000`

## Platforms

Default scan runs: **LinkedIn** and **company_careers** (direct career sites).

Optional scrapers (Indeed, Naukri, InstaHyre, Wellfound) remain in the codebase but are not part of the default scan.

Platform list is defined once in `backend/platforms.py` and exposed via `GET /api/settings`.

## Architecture

```
TempoApply/
├── run.py
├── backend/
│   ├── platforms.py           # Single source of truth for scan platforms
│   ├── pipeline.py            # Scan orchestrator + job upsert
│   ├── scrapers/
│   │   ├── registry.py        # Platform → scraper mapping
│   │   ├── filter_utils.py    # Experience & title filters
│   │   ├── linkedin.py
│   │   ├── indeed.py
│   │   ├── naukri.py
│   │   ├── instahyre.py
│   │   ├── wellfound.py       # Optional (not in default scan)
│   │   └── company_careers.py # Greenhouse / Lever / Workday
│   ├── applier/
│   │   ├── fields.py          # Label → value resolver (shared by both apply paths)
│   │   ├── filler.py          # Playwright form filling
│   │   └── workday.py         # Workday apply flow
│   ├── db/models.py
│   └── api/
│       ├── main.py
│       └── autofill.py        # Resolver API for the browser extension
├── dashboard/
│   ├── app/(dashboard)/       # Jobs, Analytics, Settings
│   ├── components/            # Sidebar, JobRow, UI primitives
│   └── lib/                   # api.ts, types, platforms
└── extension/                 # Chrome extension — assisted autofill
    ├── src/                   # scraper, filler, widget, service worker
    └── test/                  # Workday/Glassdoor/Greenhouse harness
```

## Browser extension

A Simplify-style autofill panel for applications you open yourself. Click
**Autofill**, review what it wrote, submit it by hand. Load it from
`chrome://extensions` → Developer mode → **Load unpacked** → `extension/`.

It carries no rules of its own: it scrapes the form, posts the labels to
`/api/autofill/resolve`, and writes back what the backend answers — the same
`backend/applier/fields.py` resolver the headless auto-apply uses. Handles
Workday's listbox widgets, forms embedded in an iframe (Glassdoor, Greenhouse
boards), react-select comboboxes, radio groups and the resume upload; leaves
subjective questions to you and flags them. See `extension/README.md`.

```bash
python extension/test/run_tests.py                # headless, no install needed
python extension/test/run_tests.py --integration  # real extension in Chrome
```

## Features

- Hard experience boundary (<2 years) and senior title exclusion
- Multi-platform parallel scraping via registry
- Apple-inspired dashboard with light/dark mode
- Assisted autofill on any job portal via the browser extension
- Manual job add, status tracking, analytics

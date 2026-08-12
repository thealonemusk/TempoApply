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
│   ├── db/models.py
│   └── api/main.py
└── dashboard/
    ├── app/(dashboard)/       # Jobs, Analytics, Settings
    ├── components/            # Sidebar, JobRow, UI primitives
    └── lib/                   # api.ts, types, platforms
```

## Features

- Hard experience boundary (<2 years) and senior title exclusion
- Multi-platform parallel scraping via registry
- Apple-inspired dashboard with light/dark mode
- Manual job add, status tracking, analytics

# 🗞️ TempoApply — Entry-Level Job Search Engine (<2 Yrs Exp)

**Automated multi-platform job discovery engine.** Scrapes early-career software engineering jobs across LinkedIn, Indeed, Naukri, InstaHyre, and top Indian company career sites, enforcing strict title and experience filters to retain only postings requiring **<2 years of experience**.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Configure preferences

```bash
# Copy example configuration if needed
cp config/.env.example config/.env
```

### 2. Start Backend API

```bash
# Install dependencies
pip install -r backend/requirements.txt
python -m playwright install chromium

# Start the backend server
python run.py
```
*API runs at `http://localhost:8000`*

### 3. Start Dashboard

```bash
cd dashboard
npm install
npm run dev
```
*Dashboard runs at `http://localhost:3000`*

---

## 📋 Features

| Feature | Description | Status |
|---|---|---|
| **Hard Experience Boundary (<2 Yrs)** | Automatically excludes roles requiring >=3+ years of experience | ✅ |
| **Senior Title Exclusion Filter** | Rejects `Senior`, `Lead`, `Staff`, `Architect`, `Manager`, `SDE-2`, `Level 2+` roles | ✅ |
| **LinkedIn Job Discovery** | Harvester targeting entry-level software roles | ✅ |
| **Indeed India Scraper** | Search and details extraction for fresh postings | ✅ |
| **Naukri.com Scraper** | Public listing harvesting filtered by 0-to-2 years experience | ✅ |
| **InstaHyre Scraper** | Tech startup opportunity discovery | ✅ |
| **Direct Company Career Sites** | Greenhouse & Lever API scraper for top Indian tech companies | ✅ |
| **Clean Real-Time Dashboard** | Filter, search, and track status across platforms | ✅ |

---

## 🏗️ Architecture

```
TempoApply/
├── run.py                       ← Main backend entrypoint
├── backend/
│   ├── config.py                ← Application settings (reads config/.env)
│   ├── pipeline.py              ← Job discovery & deduplication orchestrator
│   ├── scrapers/
│   │   ├── base.py              ← Standard job schema & browser helpers
│   │   ├── filter_utils.py      ← Hard experience (<2 yrs) & title filter regexes
│   │   ├── linkedin.py          ← LinkedIn scraper
│   │   ├── indeed.py            ← Indeed scraper
│   │   ├── naukri.py            ← Naukri scraper
│   │   ├── instahyre.py         ← InstaHyre scraper
│   │   └── company_careers.py   ← Greenhouse / Lever direct careers scraper
│   ├── db/models.py             ← SQLite Job database model
│   └── api/main.py              ← FastAPI REST endpoints
├── dashboard/                   ← Next.js Dashboard UI
│   └── app/
│       ├── page.tsx             ← Job search & discovery table
│       ├── analytics/           ← Pipeline analytics & status breakdown
│       └── settings/            ← Target roles & location preferences
└── config/
    └── .env                     ← Environment configuration
```

# 🗞️ TempoApply — AI Job Application Agent

**Your personal AI-powered job hunting command centre.** Scrapes jobs from LinkedIn, Indeed, Naukri and InstaHyre, scores them for fit using Gemini AI, tailors your LaTeX resume per job, generates cold emails and LinkedIn messages, and manages everything through a beautiful newspaper-themed dashboard.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Google Gemini API key (free at [aistudio.google.com](https://aistudio.google.com/app/apikey))

### 1. Configure credentials

```bash
# Copy the example env file
cp config/.env.example config/.env
# Then edit config/.env with your real credentials
```

### 2. Upload your resume
Put your `.tex` resume file in the `resumes/` folder and name it `base_resume.tex`, **OR** upload it via the dashboard.

### 3. Start the backend API

```bash
# Install Python dependencies (already done if you followed setup)
pip install -r backend/requirements.txt
python -m playwright install chromium

# Start the API server
python run.py
```

API runs at `http://localhost:8000`

### 4. Start the dashboard

```bash
cd dashboard
npm install
npm run dev
```

Dashboard at `http://localhost:3000`

---

## 📋 Features

| Feature | Status |
|---|---|
| Job scraping — LinkedIn | ✅ |
| Job scraping — Indeed | ✅ |
| Job scraping — Naukri | ✅ |
| Job scraping — InstaHyre | ✅ |
| AI job scoring (Gemini 1.5 Flash) | ✅ |
| LaTeX resume tailoring per job | ✅ |
| ATS keyword optimization | ✅ |
| Cold email generation | ✅ |
| LinkedIn message generation | ✅ |
| Cover letter generation | ✅ |
| Kanban pipeline dashboard | ✅ |
| Analytics & charts | ✅ |
| Settings UI with .env write | ✅ |
| Manual job add + analysis | ✅ |
| Auto-apply (Easy Apply) | 🔜 Coming soon |

---

## 🏗️ Architecture

```
TempoApply/
├── run.py                  ← Start backend here
├── backend/
│   ├── config.py           ← Settings (reads config/.env)
│   ├── pipeline.py         ← Main orchestrator
│   ├── ai/
│   │   ├── analyzer.py     ← Job fit scoring (Gemini)
│   │   ├── resume_tailor.py← Resume tailoring (Gemini)
│   │   ├── cold_email.py   ← Email/message/cover letter gen
│   │   └── latex_parser.py ← .tex → plaintext parser
│   ├── scrapers/
│   │   ├── linkedin.py     ← LinkedIn scraper
│   │   ├── indeed.py       ← Indeed scraper
│   │   ├── naukri.py       ← Naukri scraper
│   │   └── instahyre.py    ← InstaHyre scraper
│   ├── db/models.py        ← SQLite models (Job, Application, Resume)
│   └── api/main.py         ← FastAPI REST API
├── dashboard/              ← Next.js newspaper-themed UI
│   └── app/
│       ├── page.tsx        ← Pipeline kanban board
│       ├── outreach/       ← Cold email viewer
│       ├── resume/         ← Resume upload/management
│       ├── analytics/      ← Charts & stats
│       └── settings/       ← Credentials & preferences
├── resumes/
│   ├── base_resume.tex     ← YOUR RESUME HERE
│   └── tailored/           ← AI-tailored versions (auto-generated)
└── config/
    └── .env                ← Your secrets (not committed to git)
```

---

## 🎮 How to Use

1. **Open Settings** (`/settings`) → enter your Gemini API key + platform credentials
2. **Upload Resume** (`/resume`) → drag & drop your `.tex` resume
3. **Click "Run Scan"** in the sidebar → starts scraping all platforms in background
4. **View Pipeline** → jobs appear in the Kanban board, colour-coded by score
5. **Click "Generate AI"** on any card → Gemini tailors your resume + writes outreach
6. **Open Outreach** (`/outreach`) → select job → copy cold email / LinkedIn message

---

## 🔑 Minimum Required Config

```env
GEMINI_API_KEY=your_key
LINKEDIN_EMAIL=you@email.com
LINKEDIN_PASSWORD=yourpassword
USER_FULL_NAME=Your Name
TARGET_ROLES=Software Engineer,Backend Engineer
```

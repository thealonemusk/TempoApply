# TempoApply

Job discovery and auto-apply for early-career software roles in India. Scrapes LinkedIn, Naukri and company career sites (Greenhouse, Lever, Workday, Ashby), filters hard on experience and location, then fills and submits the applications it can actually reach.

## Quick start

```bash
pip install -r backend/requirements.txt
python -m playwright install chromium
python run.py                      # API on http://localhost:8000

cd dashboard && npm install && npm run dev    # UI on http://localhost:3000
```

## The one thing to understand

Auto-apply only works where there is a form to fill. Every job is classified into an **apply route**:

| Route | Meaning |
|---|---|
| `greenhouse` / `lever` / `workday` / `ashby` | A real form the engine can fill and submit |
| `linkedin_easy` | LinkedIn Easy Apply, filled in place |
| `manual` | No reachable form — you have to open it yourself |

Aggregator postings are usually `manual`: LinkedIn keeps the employer's form behind a login, so there is nothing to automate. **Career-site scans are what produce auto-appliable jobs.** The dashboard shows this split on every screen, and a run marks `manual` jobs immediately instead of spending a timeout per job discovering it.

## Architecture

```
run.py
backend/
├── runtime/events.py       # Run-progress contract (RunTracker + SSE broker)
├── pipeline.py             # Scan orchestrator, dedupe, upsert
├── platforms.py            # Scan platform list
├── scrapers/
│   ├── registry.py         # platform -> scraper
│   ├── filter_utils.py     # experience / location / frontend filters
│   ├── scoring.py          # heuristic relevance score
│   ├── company_list.py     # career-site metadata (~93 active boards)
│   ├── linkedin.py         # also resolves ATS links out of posting HTML
│   ├── naukri.py, indeed.py, instahyre.py, wellfound.py
│   └── company_careers.py  # Greenhouse / Lever / Workday / custom
├── applier/
│   ├── engine.py           # Worker pool, per-job timeouts, state reconcile
│   ├── ats.py              # ATS detection + apply-route classification
│   ├── adapters.py         # Per-ATS apply flows
│   ├── filler.py           # Generic form discovery and filling
│   ├── fields.py           # Label -> profile value mapping (no LLM)
│   ├── workday.py          # Workday sign-in + wizard
│   └── linkedin_apply.py   # LinkedIn session and Easy Apply
└── api/main.py             # REST + SSE
dashboard/
├── app/(app)/              # Overview, Jobs, Runs, Settings
├── components/             # Shell, JobTable, RunTimeline, UI primitives
└── lib/                    # api, hooks (SSE), runs contract, types
```

## Run progress

Both pipelines report through one contract (`backend/runtime/events.py`, mirrored in `dashboard/lib/runs.ts`):

- `GET /api/{apply,scan}/run` — snapshot for first paint
- `GET /api/{apply,scan}/stream` — SSE frames: `snapshot`, `run`, `job`, `step`, `end`

Every apply attempt carries a **step trace** — which ATS it reached, whether sign-in worked, how many fields were filled, whether submit was confirmed — plus a screenshot on failure at `GET /api/apply/screenshot/{job_id}`. That is what the Runs page renders.

## Apply engine

- One persistent Chrome profile (Chrome cannot open the same `user_data_dir` twice), so concurrency is **N pages in one shared context**, which also shares the LinkedIn/Workday session.
- Every job is wrapped in a hard timeout; one stuck posting cannot stall the queue.
- Preflight checks the resume and LinkedIn session up front and fails the run with a clear reason, rather than blocking for minutes on a login prompt.
- Nothing survives a run in a non-terminal state — `queued`/`running` rows are always reconciled.
- Queue order puts auto-appliable jobs first.

Tune parallelism, per-job timeout, auto-submit and headless under **Settings → Apply behaviour**.

## Filters

Hard boundaries applied at scan time, all in `backend/scrapers/filter_utils.py`:

- Experience at or below `EXPERIENCE_YEARS` (parsed from title, experience field, and JD)
- India-only locations
- No senior/lead/staff/principal titles, no internships
- No frontend-only roles
- Freshness window of `JOB_FRESHNESS_HOURS` (default 72h, `backend/job_freshness.py`)

Saved settings take effect immediately — no server restart.

## Configuration

`config/.env` (see `.env.example`) holds credentials and search preferences; `config/applicant_profile.json` holds the profile used to fill forms. Both are gitignored.

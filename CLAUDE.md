# TempoApply — working notes

Read this before changing anything. It records decisions and traps that are not
visible from the code, and the state of work in progress.

## The goal

Ashutosh runs a session; the board fetches jobs; the system selects ~30 of the
best openings (FAANG / Fortune-100 / well-known companies, right role, right
location), tailors the resume to each JD, and fills the applications. He should
not have to intervene unless genuinely necessary.

**It never submits.** Filling is automated, the final click is his. A mis-parsed
field reaching a real employer cannot be recalled.

## Hard rules

1. **No fabrication on the resume.** He has said "you can lie on my resume".
   The answer is still no, and `backend/resume/guard.py` enforces it
   deterministically — a rewrite introducing a technology, employer or number
   absent from the master `.tex` is rejected and the original bullet is kept.
   It has already caught a `45 -> 450` inflation and invented `Kafka`,
   `Terraform` and `Google`. This is a gate, not a prompt instruction. Do not
   weaken it into one.
2. **Never sign in to his real employer accounts to submit an application.**
   Credentials are for filling forms he then reviews.
3. **Secrets stay out of git and out of argv.** `config/.env` and
   `config/workday_accounts.json` are gitignored. Workday passwords are
   write-only through the API and read via `getpass` in the CLI — never pass a
   password as a command argument. A password he pasted in chat should be
   rotated.
4. **LinkedIn is manual.** Auto-apply does not work there and the extension is
   excluded from `linkedin.com` by `exclude_matches` in the manifest. LinkedIn
   fingerprints ~2,953 named extensions; the documented permanent restrictions
   attach to extension users, not to scripts driving an ordinary browser. Route
   LinkedIn jobs to manual review.
5. **Use the Write tool for backslash-heavy content, never a bash heredoc.**
   Git Bash on Windows mangles them. This has cost real time: `\\[2pt]` became
   `\[2pt]` and broke display math, and `\b` became a literal `0x08`, silently
   disabling a regex in `fill.js` for days. `scripts/audit.py` now scans for
   stray control characters because of that second one.

## Layout beyond the README

```
backend/applier/routing.py     jobs -> AUTO | LOGIN | MANUAL, before a browser opens
backend/applier/fields.py      label -> value; shared by the extension and headless apply
backend/applier/filler.py      Playwright form filling, combobox driving
backend/applier/workday_creds.py   per-tenant logins
backend/autopilot/select.py    company tiering (FAANG/ELITE/STRONG/KNOWN/UNKNOWN/EXCLUDED)
backend/resume/texdoc.py       .tex -> frozen source + editable slots; splice render
backend/resume/guard.py        fabrication gate
backend/resume/match.py        keyword coverage, word-boundary matching
backend/resume/compile.py      Tectonic wrapper + ATS audit
extension/src/scrape.js        form scraping, repeating-section inference
extension/src/fill.js          React-safe writes, listbox driving
dashboard/app/(autopilot)/     separate route group — must not disturb the dashboard
scripts/audit.py               repo health; run it before declaring anything done
```

## Design decisions that look arbitrary but are not

- **The LLM never emits LaTeX.** The `.tex` is split into a frozen part and
  editable prose slots; only plain text goes out and comes back. An earlier
  version of this feature asked the model for a whole LaTeX document and
  produced files that would not compile. A no-edit round trip must stay
  byte-identical — that is the parser's correctness test.
- **`\kern0pt` is the ligature breaker**, not `{}`. XeTeX shapes straight
  through empty groups. Ligature glyphs (U+FB00–FB04) break ATS keyword
  matching, so `fi`/`ffi`/`fl` in words like *workflow* must be split.
- **`:not(.iti__country)` in the option selector is load-bearing.** Roughly 240
  hidden phone-country rows sort first and consume the scan window, making
  every dropdown look like it never opened. I removed it once by accident; do
  not remove it again.
- **`custom_answer()` is longest-needle-wins.** Dict order once answered
  *"Are you subject to any employment agreements…"* with `"Paytm"`.
- **Word boundaries everywhere.** This is the repo's recurring bug class:
  `"go"` matched *google*, `"in, "` matched *"Dublin, Dublin"* and let Ireland
  through the India filter, `"india"` matched *Indian*.
- **Repeating Workday fields** are resolved from the container id where the
  tenant uses familiar names, and otherwise by repetition order — the second
  "Company" on the page is employer 2. Without the fallback, Company / Role
  Description / URL come back blank on unfamiliar tenants.
- **Tailored PDFs live in `resumes/tailored/<sub>/`, never `resumes/`.**
  `ApplicantProfile.resume_file()` globs `resumes/*` non-recursively, so a
  stray PDF there silently hijacks the default resume for every application.
- **Honeypots are skipped, not blanked.** `is_skip_field()` returns
  `action="skip"`; the extension skips at `fill.js:257`. Intel's form has a
  `beecatcher` field that silently discards the application if filled.

## Verification

All three are green as of the last sweep. Run them before claiming work is done.

```bash
python scripts/audit.py                  # imports, deps, wiring, control chars, secrets
python backend/resume/test_resume.py     # 73 checks
python extension/test/run_tests.py       # 55 checks
python extension/test/run_tests.py --integration   # real Chrome
```

`scripts/audit.py` checks the defect classes that have actually bitten this
repo, not generic lint. It caught real dependency drift: `openai`, `PyMuPDF`
and `pylatexenc` were imported but undeclared, so a fresh clone could not run
the tailorer.

Operator CLIs: `scripts/workday_login.py`, `scripts/check_ai_key.py`,
`scripts/verify_boards.py`. For an unfamiliar Workday tenant, paste
`extension/test/diagnose-workday.js` into the DevTools console on the failing
step — it is read-only and reports the real ids, Add buttons, and derived
labels.

## Running it

```bash
python run.py                  # backend on :8000
cd dashboard && npm run dev    # dashboard on :3000
```

If `run.py` dies with `[Errno 10048] ... only one usage of each socket
address`, an older server is still holding the port. **Check its start time
before assuming it is fine** — a process from a previous day serves stale code,
and the extension will keep autofilling through the old resolver. Kill it and
restart rather than reusing it.

After changing the extension: reload it at `chrome://extensions`, then
hard-refresh any job tab already open — the old content script stays resident
in those pages.

## State as of 2026-09-18

Committed and pushed on `Working-V3` through `068e871`; working tree clean.

Working and verified against a live server: routing, the autofill resolver
(legal questions, honeypots, employer 1 vs 2, websites, country), resume
tailoring with compile/audit/trim, per-tenant Workday credentials, the isolated
`/autopilot` route group, and extension UI restyled to the dashboard's tokens.

Known unfinished — none of these are started, and none should be started
without asking:

- Google scraper returns 0 results (selectors are stale). Microsoft returns 3
  and is untested since the location-filter fix.
- `_committed()` cannot read back the `#country` widget, so that field is
  filled but unverified.
- No UI for Workday accounts on `/autopilot`; `scripts/workday_login.py` is the
  only way in.
- Cover letters (`Application.cover_letter`) are still unwritten.
- `_role_matches` cuts about 94% of India engineering roles. Whether that
  threshold is right is his call, not a bug to silently "fix".

Blocked on him: OpenAI credits, and Workday signups for the tenants he wants to
apply to (Workday requires a per-employer account before a form is reachable).

## How he wants the work done

He reads the code and will spot a broken flow by looking at it — he predicted
the dead apply path from `engine.py` before any test caught it. His words:
*"write like a principal engineer who slaps himself for every broken flow"*.
Validate the critical path rather than widening surface area, and do not report
something as working until it has actually been run.

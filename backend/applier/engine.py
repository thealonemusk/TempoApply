"""
Apply orchestrator.

One persistent Chrome profile (Chrome refuses to open the same user_data_dir
twice), so concurrency comes from N pages inside a single shared context —
which has the side benefit of sharing the LinkedIn / Workday session cookies
across workers.

Shape of a run:

    preflight (resume + LinkedIn session, bounded)
      -> queue every eligible job
      -> N workers, each owning one page, each job wrapped in a hard timeout
      -> reconcile: nothing may be left 'queued' or 'running'

Progress is reported through RunTracker (backend/runtime/events.py) so the
dashboard can stream it; the DB keeps the durable per-job outcome.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import async_playwright
from sqlalchemy import or_

from backend.applier.adapters import LOG_DIR, apply_on_page
from backend.applier.ats import apply_method, detect_ats, is_auto_appliable
from backend.applier.control import clear_stop, should_stop
from backend.applier.linkedin_apply import linkedin_session_state
from backend.applier.profile import ApplicantProfile, ensure_resume_pdf, load_profile
from backend.db.models import Application, Job, SessionLocal
from backend.runtime.events import RunTracker
from backend.scrapers.base import create_browser_context

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SKIP_STATUSES = {"applied", "interviewing", "rejected", "offer", "ignored"}
MANUAL_APPLY_STATUSES = {"failed", "needs_review", "skipped"}

# A single posting should never be allowed to stall the queue. Workday's
# multi-step wizard is the slowest legitimate flow at ~2 min.
DEFAULT_JOB_TIMEOUT_SEC = 240
DEFAULT_CONCURRENCY = 2
MAX_CONCURRENCY = 4
# Politeness gap between jobs on the *same* worker.
DELAY_BETWEEN_JOBS_SEC = 3.0
# Preflight only: we do not block a whole run for minutes waiting on a login.
LINKEDIN_PREFLIGHT_WAIT_SEC = 45

_active_context = None


@dataclass
class ApplyConfig:
    concurrency: int = DEFAULT_CONCURRENCY
    job_timeout_sec: int = DEFAULT_JOB_TIMEOUT_SEC
    auto_submit: bool = True
    headless: bool = False
    skip_unsupported: bool = True

    def normalised(self) -> "ApplyConfig":
        return ApplyConfig(
            concurrency=max(1, min(MAX_CONCURRENCY, int(self.concurrency or 1))),
            job_timeout_sec=max(60, int(self.job_timeout_sec or DEFAULT_JOB_TIMEOUT_SEC)),
            auto_submit=bool(self.auto_submit),
            headless=bool(self.headless),
            skip_unsupported=bool(self.skip_unsupported),
        )


# ── browser lifecycle ────────────────────────────────────────────────────────

async def close_apply_browser() -> None:
    """Called by /api/apply/stop to unblock a run parked on a page wait."""
    ctx = _active_context
    if ctx is None:
        return
    try:
        await ctx.close()
    except Exception:
        pass


# ── job selection ────────────────────────────────────────────────────────────

def eligible_jobs(db, job_ids: Optional[List[str]] = None) -> List[Job]:
    q = db.query(Job)
    if job_ids:
        q = q.filter(Job.id.in_(job_ids))
    else:
        q = q.filter(~Job.status.in_(SKIP_STATUSES))
        q = q.filter(
            or_(
                Job.apply_status.is_(None),
                Job.apply_status == "",
                ~Job.apply_status.in_({"applied"} | MANUAL_APPLY_STATUSES),
            )
        )
    jobs = q.order_by(Job.relevance_score.desc()).all()
    if job_ids:
        jobs = [j for j in jobs if j.status not in SKIP_STATUSES]
    # Auto-appliable postings first, best score within each group, so a long
    # queue spends its time where submissions can actually land.
    jobs.sort(key=lambda j: (0 if is_auto_appliable(_method(j)) else 1,
                             -(j.relevance_score or 0.0)))
    return jobs


def _method(job: Job) -> str:
    return apply_method(
        url=job.url,
        apply_url=job.apply_url or "",
        ats_type=job.ats_type or "",
        easy_apply=bool(job.easy_apply),
        platform=job.platform or "",
    )


# ── durable outcome ──────────────────────────────────────────────────────────
# These helpers contain no awaits, so concurrent workers can never interleave
# inside one of them and corrupt the shared Session.

def _mark_queued(db, jobs: List[Job]) -> None:
    for job in jobs:
        job.apply_status = "queued"
        job.apply_error = ""
        if not job.ats_type:
            job.ats_type = detect_ats(job.url)
    db.commit()


def _mark_running(db, job_id: str) -> None:
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.apply_status = "running"
        db.commit()


def _record_result(db, job_id: str, result: Dict[str, Any]) -> None:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return
    status = result.get("status") or "failed"
    message = result.get("message") or ""
    job.ats_type = result.get("ats") or job.ats_type or detect_ats(job.url)
    job.apply_status = status
    job.apply_error = message
    if status == "applied":
        job.status = "applied"
        job.applied_at = datetime.utcnow()
        if not job.application:
            db.add(Application(job_id=job.id, notes=message))
        else:
            job.application.notes = message
    db.commit()


def _reconcile_unfinished(db, reason: str) -> List[str]:
    """Nothing may survive a run in a non-terminal state."""
    stuck = db.query(Job).filter(Job.apply_status.in_(["queued", "running"])).all()
    ids = []
    for job in stuck:
        job.apply_status = "skipped"
        job.apply_error = reason
        ids.append(job.id)
    if ids:
        db.commit()
    return ids


def _screenshot_for(job_id: str) -> str:
    """Relative path of whatever the adapters captured for this job, if any."""
    for name in (f"{job_id}.png", f"{job_id}-filled.png"):
        if (LOG_DIR / name).is_file():
            return f"data/apply_logs/{name}"
    return ""


# ── a single job attempt ─────────────────────────────────────────────────────

async def _apply_one(
    page,
    job: Job,
    profile: ApplicantProfile,
    resume,
    auto_submit: bool,
    report,
) -> Dict[str, Any]:
    # A URL resolved during the scan lets us go straight to the company form
    # instead of clicking through the aggregator again.
    start_url = (job.apply_url or "").strip() or job.url
    if start_url != job.url:
        report("info", f"using ATS link resolved at scan time: {start_url}", True)

    return await apply_on_page(
        page=page,
        url=start_url,
        profile=profile,
        resume=resume,
        job_title=f"{job.title} ({job.location})" if job.location else job.title,
        company=job.company,
        auto_submit=auto_submit,
        job_id=job.id,
        jd_text=job.jd_text or "",
        report=report,
    )


async def _close_worker_pages(context, keep) -> None:
    """Adapters open company tabs; close everything this worker no longer needs."""
    for extra in list(context.pages):
        if extra is keep or extra.is_closed():
            continue
        try:
            await extra.close()
        except Exception:
            pass


# ── the run ──────────────────────────────────────────────────────────────────

async def run_apply_pipeline(
    job_ids: Optional[List[str]] = None,
    auto_submit: bool = True,
    headless: bool = False,
    concurrency: int = DEFAULT_CONCURRENCY,
    job_timeout_sec: int = DEFAULT_JOB_TIMEOUT_SEC,
    skip_unsupported: bool = True,
) -> Dict[str, Any]:
    cfg = ApplyConfig(
        concurrency=concurrency,
        job_timeout_sec=job_timeout_sec,
        auto_submit=auto_submit,
        headless=headless,
        skip_unsupported=skip_unsupported,
    ).normalised()

    profile = load_profile()
    # The resume is generated during preflight if missing, so it is not blocking here.
    missing = [m for m in profile.missing_required() if m != "resume"]

    tracker = RunTracker(
        "apply",
        concurrency=cfg.concurrency,
        meta={"auto_submit": cfg.auto_submit, "headless": cfg.headless, "phase": "starting"},
    )

    if missing:
        return tracker.finish(
            "error",
            message="Profile incomplete: " + ", ".join(missing),
            error="profile_incomplete",
        )

    global _active_context
    clear_stop()
    db = SessionLocal()

    try:
        jobs = eligible_jobs(db, job_ids)
        if not jobs:
            return tracker.finish("done", message="No eligible jobs to apply to")

        for job in jobs:
            tracker.add_job(
                job.id,
                title=job.title,
                company=job.company,
                url=job.url,
                ats=job.ats_type or detect_ats(job.apply_url or job.url),
            )
        _mark_queued(db, jobs)

        # A posting with no reachable form (staffing portal, bespoke careers
        # page behind auth) cannot be auto-submitted. Resolve those up front
        # so the run does not spend a full timeout per job discovering it.
        attempt: List[Job] = []
        unsupported: List[Job] = []
        for job in jobs:
            if cfg.skip_unsupported and not is_auto_appliable(_method(job)):
                unsupported.append(job)
            else:
                attempt.append(job)

        for job in unsupported:
            note = "No supported application form — apply manually"
            _record_result(db, job.id, {"status": "skipped", "message": note,
                                        "ats": job.ats_type or ""})
            tracker.step(job.id, "detect", "no supported ATS on this posting", False)
            tracker.finish_job(job.id, "skipped", note, ats=job.ats_type or "")

        tracker.set_meta(
            auto_appliable=len(attempt),
            manual_only=len(unsupported),
        )

        if not attempt:
            return tracker.finish(
                "done",
                message=(
                    f"{len(unsupported)} job(s) have no supported application form — "
                    "apply to those manually"
                ),
            )

        jobs = attempt
        queue: asyncio.Queue = asyncio.Queue()
        for job in jobs:
            queue.put_nowait(job.id)
        by_id = {job.id: job for job in jobs}

        async with async_playwright() as playwright:
            browser, context = await create_browser_context(playwright, headless=cfg.headless)
            _active_context = context
            try:
                # ── preflight ────────────────────────────────────────────
                tracker.set_meta(phase="preflight")
                pages = [p for p in context.pages if not p.is_closed()]
                lead = pages[0] if pages else await context.new_page()

                resume = await ensure_resume_pdf(lead, profile)
                if not resume:
                    return tracker.finish(
                        "error",
                        message="Could not find or generate a resume PDF",
                        error="no_resume",
                    )

                if should_stop():
                    skipped = _reconcile_unfinished(db, "Stopped by user")
                    for jid in skipped:
                        tracker.finish_job(jid, "skipped", "Stopped by user")
                    return tracker.finish("stopped", message="Stopped by user")

                signed_in, detail = await linkedin_session_state(
                    lead, wait_seconds=LINKEDIN_PREFLIGHT_WAIT_SEC
                )
                tracker.set_meta(linkedin_signed_in=signed_in)
                if not signed_in:
                    skipped = _reconcile_unfinished(db, "LinkedIn sign-in required")
                    for jid in skipped:
                        tracker.finish_job(jid, "skipped", "LinkedIn sign-in required")
                    return tracker.finish(
                        "error",
                        message=(
                            "LinkedIn is not signed in. Sign in inside the TempoApply "
                            f"Chrome window, then start the run again. ({detail})"
                        ),
                        error="linkedin_signin_required",
                    )

                # ── workers ──────────────────────────────────────────────
                tracker.set_meta(phase="applying")
                worker_count = min(cfg.concurrency, len(jobs))
                pool_pages = [lead]
                for _ in range(worker_count - 1):
                    pool_pages.append(await context.new_page())

                async def worker(index: int, page) -> None:
                    while True:
                        if should_stop():
                            return
                        try:
                            job_id = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            return

                        job = by_id[job_id]
                        method = _method(job)
                        ats_guess = job.ats_type or detect_ats(job.apply_url or job.url)
                        tracker.start_job(job_id, ats=ats_guess)
                        tracker.step(job_id, "detect", f"apply method: {method}", True)
                        _mark_running(db, job_id)

                        def report(kind: str, detail: str = "", ok: Optional[bool] = None,
                                   _jid: str = job_id) -> None:
                            tracker.step(_jid, kind, detail, ok)

                        try:
                            result = await asyncio.wait_for(
                                _apply_one(page, job, profile, resume, cfg.auto_submit, report),
                                timeout=cfg.job_timeout_sec,
                            )
                        except asyncio.TimeoutError:
                            report("error", f"Timed out after {cfg.job_timeout_sec}s", False)
                            result = {
                                "status": "failed",
                                "message": f"Timed out after {cfg.job_timeout_sec}s",
                                "ats": ats_guess,
                            }
                        except Exception as exc:
                            if should_stop():
                                result = {
                                    "status": "skipped",
                                    "message": "Stopped by user",
                                    "ats": ats_guess,
                                }
                            else:
                                logger.exception(f"Apply failed for {job.title} @ {job.company}")
                                report("error", str(exc), False)
                                result = {
                                    "status": "failed",
                                    "message": str(exc),
                                    "ats": ats_guess,
                                }

                        _record_result(db, job_id, result)
                        tracker.finish_job(
                            job_id,
                            state=result.get("status") or "failed",
                            message=result.get("message") or "",
                            ats=result.get("ats") or ats_guess,
                            screenshot=_screenshot_for(job_id),
                            final_url=result.get("final_url") or "",
                        )
                        logger.info(
                            f"[w{index}] {job.title} @ {job.company}: {result.get('status')}"
                        )

                        await _close_worker_pages(context, page)
                        queue.task_done()

                        if not queue.empty() and not should_stop():
                            await asyncio.sleep(DELAY_BETWEEN_JOBS_SEC)

                await asyncio.gather(
                    *(worker(i, p) for i, p in enumerate(pool_pages)),
                    return_exceptions=True,
                )
            finally:
                _active_context = None
                for closer in (context, browser):
                    if closer is None:
                        continue
                    try:
                        await closer.close()
                    except Exception:
                        pass

        stopped = should_stop()
        reason = "Stopped by user" if stopped else "Run ended before this job started"
        for jid in _reconcile_unfinished(db, reason):
            tracker.finish_job(jid, "skipped", reason)

        totals = tracker.state.totals
        return tracker.finish(
            "stopped" if stopped else "done",
            message=(
                "Stopped by user"
                if stopped
                else f"{totals.get('applied', 0)} applied, "
                f"{totals.get('needs_review', 0)} need review, "
                f"{totals.get('failed', 0)} failed"
            ),
        )
    except Exception as exc:
        logger.exception("Apply run crashed")
        for jid in _reconcile_unfinished(db, f"Run error: {exc}"):
            tracker.finish_job(jid, "skipped", "Run error")
        return tracker.finish("error", message=str(exc), error="run_crashed")
    finally:
        db.close()

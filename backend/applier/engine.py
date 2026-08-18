"""Apply orchestrator: one browser, sequential jobs, DB status updates."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger
from playwright.async_api import async_playwright

from sqlalchemy import or_

from backend.applier.adapters import LOG_DIR, apply_on_page
from backend.applier.ats import detect_ats
from backend.applier.control import clear_stop, should_stop
from backend.applier.filler import screenshot_failure
from backend.applier.linkedin_apply import ensure_linkedin_session
from backend.applier.profile import ApplicantProfile, ensure_resume_pdf, load_profile
from backend.db.models import Application, Job, SessionLocal
from backend.scrapers.base import create_browser_context

SKIP_STATUSES = {"applied", "interviewing", "rejected", "offer", "ignored"}
MANUAL_APPLY_STATUSES = {"failed", "needs_review", "skipped"}
DELAY_BETWEEN_JOBS_SEC = 8
_active_context = None


async def _reuse_page(context):
    pages = [p for p in context.pages if not p.is_closed()]
    return pages[0] if pages else await context.new_page()


async def _close_extra_pages(context, keep) -> None:
    for extra in list(context.pages):
        if extra != keep:
            try:
                await extra.close()
            except Exception:
                pass


async def close_apply_browser() -> None:
    ctx = _active_context
    if ctx is None:
        return
    try:
        await ctx.close()
    except Exception:
        pass


def _skip_unfinished(db, jobs: List[Job], summary: Dict) -> None:
    for job in jobs:
        fresh = db.query(Job).filter(Job.id == job.id).first()
        if not fresh or fresh.apply_status not in {"queued", "applying"}:
            continue
        fresh.apply_status = "skipped"
        fresh.apply_error = "Stopped by user"
        summary["skipped"] = summary.get("skipped", 0) + 1
        summary["results"].append({
            "job_id": fresh.id,
            "title": fresh.title,
            "company": fresh.company,
            "status": "skipped",
            "message": "Stopped by user",
            "ats": fresh.ats_type or "",
        })
    db.commit()
    summary["message"] = "Stopped by user"


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
    return jobs


def _record_result(db, job: Job, result: Dict) -> None:
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


async def apply_one_job(
    page,
    job: Job,
    profile: ApplicantProfile,
    resume,
    auto_submit: bool,
) -> Dict:
    try:
        return await apply_on_page(
            page=page,
            url=job.url,
            profile=profile,
            resume=resume,
            job_title=f"{job.title} ({job.location})" if job.location else job.title,
            company=job.company,
            auto_submit=auto_submit,
            job_id=job.id,
            jd_text=job.jd_text or "",
        )
    except Exception as exc:
        if should_stop():
            return {"status": "skipped", "message": "Stopped by user", "ats": detect_ats(job.url)}
        logger.exception(f"Apply failed for {job.title} @ {job.company}")
        await screenshot_failure(page, LOG_DIR / f"{job.id}.png")
        return {"status": "failed", "message": str(exc), "ats": detect_ats(job.url)}


async def run_apply_pipeline(
    job_ids: Optional[List[str]] = None,
    auto_submit: bool = True,
    headless: bool = False,
) -> Dict:
    profile = load_profile()
    missing = profile.missing_required()
    # Resume can be generated after the browser starts
    missing = [m for m in missing if m != "resume"]
    if missing:
        return {
            "error": "Profile incomplete: " + ", ".join(missing),
            "applied": 0,
            "failed": 0,
            "needs_review": 0,
            "skipped": 0,
        }

    db = SessionLocal()
    summary = {
        "applied": 0,
        "failed": 0,
        "needs_review": 0,
        "skipped": 0,
        "results": [],
    }
    global _active_context
    clear_stop()
    try:
        jobs = eligible_jobs(db, job_ids)
        if not jobs:
            summary["message"] = "No eligible jobs to apply to"
            return summary

        for job in jobs:
            job.apply_status = "queued"
            job.apply_error = ""
            if not job.ats_type:
                job.ats_type = detect_ats(job.url)
        db.commit()

        async with async_playwright() as playwright:
            browser, context = await create_browser_context(playwright, headless=headless)
            _active_context = context
            page = await _reuse_page(context)
            try:
                if should_stop():
                    _skip_unfinished(db, jobs, summary)
                    return summary
                resume = await ensure_resume_pdf(page, profile)
                signed_in = await ensure_linkedin_session(page)
                if not resume:
                    return {**summary, "error": "Could not create or find a resume PDF"}
                if should_stop():
                    _skip_unfinished(db, jobs, summary)
                    return summary
                if not signed_in:
                    return {
                        **summary,
                        "error": "LinkedIn not signed in. Use the TempoApply Chrome window, then retry.",
                    }

                for i, job in enumerate(jobs):
                    if should_stop():
                        _skip_unfinished(db, jobs, summary)
                        return summary
                    fresh = db.query(Job).filter(Job.id == job.id).first()
                    if not fresh:
                        continue
                    fresh.apply_status = "applying"
                    db.commit()

                    page = await _reuse_page(context)
                    result = await apply_one_job(page, fresh, profile, resume, auto_submit)
                    await _close_extra_pages(context, page)

                    _record_result(db, fresh, result)
                    bucket = result.get("status") or "failed"
                    if bucket not in summary:
                        summary[bucket] = 0
                    summary[bucket] = summary.get(bucket, 0) + 1
                    summary["results"].append({
                        "job_id": fresh.id,
                        "title": fresh.title,
                        "company": fresh.company,
                        "status": bucket,
                        "message": result.get("message", ""),
                        "ats": result.get("ats", ""),
                    })
                    logger.info(
                        f"Apply {i + 1}/{len(jobs)} {fresh.title} @ {fresh.company}: {bucket}"
                    )
                    if should_stop():
                        _skip_unfinished(db, jobs, summary)
                        return summary
                    if i < len(jobs) - 1:
                        for _ in range(DELAY_BETWEEN_JOBS_SEC):
                            if should_stop():
                                _skip_unfinished(db, jobs, summary)
                                return summary
                            await asyncio.sleep(1)
            finally:
                _active_context = None
                try:
                    await context.close()
                except Exception:
                    pass
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass
    finally:
        db.close()

    return summary

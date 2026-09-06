"""
FastAPI REST API for the TempoApply dashboard.

Run progress (scan and apply) is exposed two ways:
  GET /api/{kind}/run     — snapshot, for first paint
  GET /api/{kind}/stream  — server-sent events, for live updates
Both speak the contract in backend/runtime/events.py.
"""
import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from loguru import logger

from backend.job_freshness import JOB_FRESHNESS_HOURS
from backend.db.models import Job, get_db, init_db
from backend.config import refresh_settings, settings
from backend.platforms import DEFAULT_SCAN_PLATFORMS, SCAN_PLATFORMS, ALL_PLATFORMS
from backend.applier.ats import apply_method, detect_ats, is_auto_appliable
from backend.applier.engine import DEFAULT_CONCURRENCY, DEFAULT_JOB_TIMEOUT_SEC, MAX_CONCURRENCY
from backend.applier.profile import RESUMES_DIR, load_profile, save_profile
from backend.runtime.events import BROKER, RunKind, current_snapshot

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
APPLY_LOG_DIR = PROJECT_ROOT / "data" / "apply_logs"


def _env_path() -> Path:
    path = PROJECT_ROOT / "config" / ".env"
    if not path.exists():
        path = PROJECT_ROOT / ".env"
    return path


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    BROKER.remember_loop()
    logger.info("TempoApply API started")
    yield


app = FastAPI(title="TempoApply API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Schemas ─────────────────────────────────────────────────────────────────

class JobOut(BaseModel):
    id: str
    title: str
    company: str
    platform: str
    url: str
    location: str
    experience_required: str
    salary_range: str
    relevance_score: float
    fit_reason: str
    missing_skills: str
    seniority_level: str
    is_engineering_role: bool
    easy_apply: bool
    recruiter_name: str
    recruiter_profile: str
    status: str
    ats_type: Optional[str] = ""
    apply_url: Optional[str] = ""
    apply_status: Optional[str] = ""
    apply_error: Optional[str] = ""
    # Derived: greenhouse | lever | workday | ashby | linkedin_easy | manual
    apply_method: str = "manual"
    auto_appliable: bool = False
    discovered_at: Optional[datetime]
    visited_at: Optional[datetime]
    applied_at: Optional[datetime]

    class Config:
        from_attributes = True

    @field_validator("ats_type", "apply_url", "apply_status", "apply_error", mode="before")
    @classmethod
    def blank_apply_fields(cls, value):
        return value or ""


class ScanRequest(BaseModel):
    platforms: List[str] = Field(default_factory=lambda: list(DEFAULT_SCAN_PLATFORMS))
    max_jobs_per_platform: int = 400
    headless: bool = True


class StatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class ApplyRequest(BaseModel):
    job_ids: Optional[List[str]] = None
    auto_submit: bool = True
    headless: bool = False
    concurrency: int = Field(default=DEFAULT_CONCURRENCY, ge=1, le=MAX_CONCURRENCY)
    job_timeout_sec: int = Field(default=DEFAULT_JOB_TIMEOUT_SEC, ge=60, le=900)
    # Postings with no reachable form are marked for manual apply immediately
    # instead of burning a full timeout each.
    skip_unsupported: bool = True


class ManualJobRequest(BaseModel):
    title: str
    company: str
    url: str
    jd_text: str
    location: str = ""
    platform: str = "manual"


def _job_row(job: Job) -> "JobOut":
    """JobOut plus the derived appliability fields. Never writes to the DB."""
    row = JobOut.model_validate(job)
    if not row.ats_type:
        row.ats_type = detect_ats(job.apply_url or job.url)
    row.apply_method = apply_method(
        url=job.url,
        apply_url=job.apply_url or "",
        ats_type=job.ats_type or "",
        easy_apply=bool(job.easy_apply),
        platform=job.platform or "",
    )
    row.auto_appliable = is_auto_appliable(row.apply_method)
    return row


# ─── Jobs ────────────────────────────────────────────────────────────────────

@app.get("/api/jobs", response_model=List[JobOut])
def get_jobs(
    status: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    max_age_hours: int = Query(JOB_FRESHNESS_HOURS, ge=1),
    db: Session = Depends(get_db),
):
    """
    All jobs, newest-relevant first. Stale discovered/scored jobs are hidden.

    This is a hot path the dashboard polls, so it is strictly read-only —
    ATS backfill lives in POST /api/jobs/backfill-ats.
    """
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    if platform:
        query = query.filter(Job.platform == platform)
    if min_score is not None:
        query = query.filter(Job.relevance_score >= min_score)

    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    query = query.filter(
        (Job.status.notin_(["discovered", "scored"])) | (Job.discovered_at >= cutoff)
    )
    jobs = query.order_by(Job.relevance_score.desc()).all()

    return [_job_row(job) for job in jobs]


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_row(job)


@app.post("/api/jobs/backfill-ats")
def backfill_ats(db: Session = Depends(get_db)):
    """Persist ats_type for rows that never had one (cheap, URL-only)."""
    updated = 0
    for job in db.query(Job).filter((Job.ats_type == "") | (Job.ats_type.is_(None))).all():
        job.ats_type = detect_ats(job.apply_url or job.url)
        updated += 1
    if updated:
        db.commit()
    return {"success": True, "updated": updated}


@app.post("/api/jobs/resolve-apply-urls")
async def resolve_apply_urls(
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Resolve the real company/ATS apply URL for aggregator postings that do not
    have one yet. New scans do this inline; this backfills existing rows.
    """
    from backend.scrapers.linkedin import _apply_url_from_html
    import requests

    candidates = (
        db.query(Job)
        .filter((Job.apply_url == "") | (Job.apply_url.is_(None)))
        .filter(Job.platform == "linkedin")
        .limit(limit)
        .all()
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def fetch(url: str, jd: str) -> str:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            return _apply_url_from_html(resp.content, jd)
        except Exception:
            return ""

    resolved = 0
    for job in candidates:
        found = await asyncio.to_thread(fetch, job.url, job.jd_text or "")
        if not found:
            continue
        job.apply_url = found
        job.ats_type = detect_ats(found)
        resolved += 1
    if resolved:
        db.commit()
    return {"success": True, "checked": len(candidates), "resolved": resolved}


@app.post("/api/jobs/manual")
def add_manual_job(req: ManualJobRequest, db: Session = Depends(get_db)):
    import uuid

    existing = db.query(Job).filter(Job.url == req.url).first()
    if existing:
        raise HTTPException(status_code=409, detail="Job with this URL already exists")

    job = Job(
        id=str(uuid.uuid4()),
        title=req.title,
        company=req.company,
        platform=req.platform,
        url=req.url,
        location=req.location,
        jd_text=req.jd_text,
        relevance_score=100.0,
        fit_reason="Manually added job posting",
        missing_skills="[]",
        seniority_level="entry",
        is_engineering_role=True,
        status="discovered",
        ats_type=detect_ats(req.url),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "score": job.relevance_score, "message": "Job added"}


@app.patch("/api/jobs/{job_id}/status")
def update_job_status(job_id: str, update: StatusUpdate, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = update.status
    if update.status == "applied":
        job.applied_at = datetime.utcnow()
    if update.notes and job.application:
        job.application.notes = update.notes
    db.commit()
    return {"success": True, "status": update.status}


@app.post("/api/jobs/{job_id}/visit")
def mark_job_visited(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.visited_at:
        job.visited_at = datetime.utcnow()
        db.commit()
    return {"success": True, "visited_at": job.visited_at}


@app.post("/api/jobs/{job_id}/reset-apply")
def reset_job_apply(job_id: str, db: Session = Depends(get_db)):
    """Clear a failed/needs-review outcome so the job re-enters the queue."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.apply_status = ""
    job.apply_error = ""
    db.commit()
    return {"success": True}


@app.delete("/api/jobs/clear")
def clear_discovered_jobs(db: Session = Depends(get_db)):
    """Delete jobs still in 'discovered' or 'scored' status."""
    jobs_to_delete = db.query(Job).filter(Job.status.in_(["discovered", "scored"])).all()
    deleted_count = 0
    for job in jobs_to_delete:
        if job.application:
            db.delete(job.application)
        db.delete(job)
        deleted_count += 1
    db.commit()
    return {"success": True, "deleted_count": deleted_count}


@app.post("/api/jobs/purge-stale")
def purge_stale_jobs(
    max_age_hours: int = Query(JOB_FRESHNESS_HOURS, ge=1),
    db: Session = Depends(get_db),
):
    from backend.pipeline import purge_stale_discovered_jobs

    purged_count = purge_stale_discovered_jobs(db, max_age_hours=max_age_hours)
    return {"success": True, "purged_count": purged_count}


@app.post("/api/jobs/purge-experienced")
def purge_experienced_jobs(db: Session = Depends(get_db)):
    """Purge jobs failing the experience, frontend, or India-location filters."""
    from backend.scrapers.filter_utils import is_career_listing_eligible, passes_hard_filters

    all_jobs = db.query(Job).all()
    purged_count = 0
    for job in all_jobs:
        if job.status in {"applied", "interviewing", "offer"}:
            continue
        job_dict = {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "experience_required": job.experience_required,
            "jd_text": job.jd_text,
            "platform": job.platform,
        }
        is_valid, _ = passes_hard_filters(job_dict, max_years=settings.experience_years)
        if is_valid and job.platform == "company_careers":
            is_valid, _ = is_career_listing_eligible(job_dict)
        if not is_valid:
            if job.application:
                db.delete(job.application)
            db.delete(job)
            purged_count += 1
    db.commit()
    return {"success": True, "purged_count": purged_count}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.application:
        db.delete(job.application)
    db.delete(job)
    db.commit()
    return {"success": True}


# ─── Run progress: snapshots + SSE ───────────────────────────────────────────

def _is_running(kind: RunKind) -> bool:
    return BROKER.current(kind).status in ("running", "stopping")


async def _event_stream(kind: RunKind):
    """SSE: one hydration snapshot, then every mutation, plus keepalives."""
    queue = BROKER.subscribe(kind)
    try:
        hydrate = {"type": "snapshot", "data": current_snapshot(kind)}
        yield f"data: {json.dumps(hydrate)}\n\n"
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield f"data: {json.dumps(frame)}\n\n"
    except asyncio.CancelledError:
        raise
    finally:
        BROKER.unsubscribe(kind, queue)


SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@app.get("/api/apply/stream")
async def apply_stream():
    return StreamingResponse(
        _event_stream("apply"), media_type="text/event-stream", headers=SSE_HEADERS
    )


@app.get("/api/scan/stream")
async def scan_stream():
    return StreamingResponse(
        _event_stream("scan"), media_type="text/event-stream", headers=SSE_HEADERS
    )


@app.get("/api/apply/run")
def apply_run():
    return current_snapshot("apply")


@app.get("/api/scan/run")
def scan_run():
    return current_snapshot("scan")


@app.get("/api/apply/screenshot/{job_id}")
def apply_screenshot(job_id: str):
    """Serve the failure/filled screenshot an adapter captured for a job."""
    for name in (f"{job_id}.png", f"{job_id}-filled.png"):
        path = APPLY_LOG_DIR / name
        if path.is_file():
            return FileResponse(path, media_type="image/png")
    raise HTTPException(status_code=404, detail="No screenshot for this job")


# ─── Scan ────────────────────────────────────────────────────────────────────

@app.post("/api/scan")
async def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    if _is_running("scan"):
        raise HTTPException(status_code=409, detail="Scan already running")
    if _is_running("apply"):
        raise HTTPException(status_code=409, detail="Apply is running — wait until it finishes")

    async def do_scan():
        from backend.scan_control import clear_stop
        from backend.pipeline import run_scan_pipeline

        clear_stop()
        try:
            await run_scan_pipeline(
                platforms=req.platforms,
                max_jobs_per_platform=req.max_jobs_per_platform,
                headless=req.headless,
            )
        except Exception as e:
            logger.exception("Scan error")
            from backend.runtime.events import BROKER as _b

            run = _b.current("scan")
            run.status = "error"
            run.error = str(e)
            _b.publish("scan", {"type": "run", "data": run.header()})

    background_tasks.add_task(do_scan)
    return {"message": "Scan started", "running": True}


@app.get("/api/scan/status")
def get_scan_status():
    """Legacy shape, kept for compatibility. Prefer /api/scan/run."""
    run = BROKER.current("scan")
    return {"running": run.status in ("running", "stopping"), "last_result": run.meta or None}


@app.post("/api/scan/stop")
def stop_scan():
    from backend.scan_control import request_stop

    if not _is_running("scan"):
        return {"message": "Scan is not running", "running": False}
    request_stop()
    run = BROKER.current("scan")
    run.status = "stopping"
    BROKER.publish("scan", {"type": "run", "data": run.header()})
    return {"message": "Stop requested", "running": True}


# ─── Applicant profile ───────────────────────────────────────────────────────

def _profile_payload() -> Dict[str, Any]:
    profile = load_profile()
    data = profile.to_dict()
    data["missing"] = profile.missing_required()
    data["has_resume"] = profile.resume_file() is not None
    data["ready_to_apply"] = not data["missing"]
    return data


@app.get("/api/profile")
def get_profile():
    return _profile_payload()


@app.put("/api/profile")
def update_profile(payload: dict):
    save_profile(payload)
    return _profile_payload()


@app.post("/api/profile/resume")
async def upload_resume_file(file: UploadFile = File(...)):
    suffix = Path(file.filename or "resume.pdf").suffix.lower()
    if suffix not in {".pdf", ".doc", ".docx"}:
        raise HTTPException(status_code=400, detail="Resume must be PDF, DOC, or DOCX")
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    dest = RESUMES_DIR / f"resume{suffix}"
    dest.write_bytes(await file.read())
    rel = f"resumes/resume{suffix}"
    save_profile({"resume_path": rel})
    return {"success": True, "resume_path": rel}


# ─── Apply ───────────────────────────────────────────────────────────────────

@app.get("/api/apply/status")
def get_apply_status():
    """Legacy shape, kept for compatibility. Prefer /api/apply/run."""
    run = BROKER.current("apply")
    running = run.status in ("running", "stopping")
    active = next((j for j in run.jobs.values() if j.state == "running"), None)
    return {
        "running": running,
        "last_result": run.header() if run.run_id else None,
        "current_job": f"{active.title} @ {active.company}" if active else None,
    }


@app.post("/api/apply/stop")
async def stop_apply():
    from backend.applier.control import request_stop
    from backend.applier.engine import close_apply_browser

    if not _is_running("apply"):
        return {"message": "Apply is not running", "running": False}
    request_stop()
    run = BROKER.current("apply")
    run.status = "stopping"
    BROKER.publish("apply", {"type": "run", "data": run.header()})
    # Closing the context unblocks any worker parked on a page wait.
    await close_apply_browser()
    return {"message": "Stop requested", "running": True}


@app.post("/api/apply")
async def start_apply(req: ApplyRequest, background_tasks: BackgroundTasks):
    if _is_running("apply"):
        raise HTTPException(status_code=409, detail="Apply already running")
    if _is_running("scan"):
        raise HTTPException(status_code=409, detail="Scan is running — wait until it finishes")

    profile = load_profile()
    missing = [m for m in profile.missing_required() if m != "resume"]
    if missing:
        raise HTTPException(
            status_code=400, detail="Profile incomplete: " + ", ".join(missing)
        )

    async def do_apply():
        from backend.applier.engine import run_apply_pipeline

        try:
            await run_apply_pipeline(
                job_ids=req.job_ids,
                auto_submit=req.auto_submit,
                headless=req.headless,
                concurrency=req.concurrency,
                job_timeout_sec=req.job_timeout_sec,
                skip_unsupported=req.skip_unsupported,
            )
        except Exception as e:
            logger.exception("Apply error")
            run = BROKER.current("apply")
            run.status = "error"
            run.error = str(e)
            BROKER.publish("apply", {"type": "run", "data": run.header()})

    background_tasks.add_task(do_apply)
    return {"message": "Apply started", "running": True}


@app.post("/api/jobs/{job_id}/apply")
async def apply_single_job(
    job_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    req = ApplyRequest(
        job_ids=[job_id],
        auto_submit=True,
        headless=False,
        concurrency=1,
        skip_unsupported=False,
    )
    return await start_apply(req, background_tasks)


# ─── Analytics ───────────────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    from sqlalchemy import func as sqlfunc

    total = db.query(Job).count()

    def group(column):
        rows = db.query(column, sqlfunc.count(Job.id)).group_by(column).all()
        return {(value or ""): count for value, count in rows}

    status_counts = group(Job.status)
    by_status = {
        s: status_counts.get(s, 0)
        for s in [
            "discovered",
            "scored",
            "tailored",
            "applied",
            "interviewing",
            "rejected",
            "offer",
        ]
    }

    platform_counts = group(Job.platform)
    by_platform = {p: platform_counts.get(p, 0) for p in ALL_PLATFORMS}

    apply_counts = {k: v for k, v in group(Job.apply_status).items() if k}
    ats_counts = {k: v for k, v in group(Job.ats_type).items() if k}

    top_companies = (
        db.query(Job.company, Job.relevance_score)
        .order_by(Job.relevance_score.desc())
        .limit(10)
        .all()
    )

    return {
        "total_jobs": total,
        "by_status": by_status,
        "by_platform": by_platform,
        "by_apply_status": apply_counts,
        "by_ats": ats_counts,
        "top_companies": [{"company": c, "score": s} for c, s in top_companies],
    }


# ─── Settings ────────────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    return {
        "target_roles": settings.target_roles_list,
        "experience_years": settings.experience_years,
        "preferred_locations": settings.preferred_locations_list,
        "min_relevance_score": settings.min_relevance_score,
        "user_full_name": settings.user_full_name,
        "excluded_companies": settings.excluded_companies_list,
        "has_gemini_key": bool(settings.gemini_api_key),
        "has_linkedin": bool(settings.linkedin_email),
        "has_naukri": bool(settings.naukri_email),
        "has_indeed": bool(settings.indeed_email),
        "has_instahyre": bool(settings.instahyre_email),
        "has_workday": bool(settings.workday_email and settings.workday_password),
        "supported_platforms": SCAN_PLATFORMS,
        "default_concurrency": DEFAULT_CONCURRENCY,
        "max_concurrency": MAX_CONCURRENCY,
        "job_freshness_hours": JOB_FRESHNESS_HOURS,
    }


# Keys written verbatim from the request when present.
_SECRET_KEYS = {
    "gemini_api_key": "GEMINI_API_KEY",
    "linkedin_email": "LINKEDIN_EMAIL",
    "linkedin_password": "LINKEDIN_PASSWORD",
    "naukri_email": "NAUKRI_EMAIL",
    "naukri_password": "NAUKRI_PASSWORD",
    "indeed_email": "INDEED_EMAIL",
    "indeed_password": "INDEED_PASSWORD",
    "instahyre_email": "INSTAHYRE_EMAIL",
    "instahyre_password": "INSTAHYRE_PASSWORD",
    "workday_email": "WORKDAY_EMAIL",
    "workday_password": "WORKDAY_PASSWORD",
}


@app.post("/api/settings")
def update_settings(new_settings: dict):
    """
    Persist settings to config/.env, then reload them in-process so the change
    takes effect without restarting the server.
    """
    env_path = _env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)

    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    updates = {
        "TARGET_ROLES": ",".join(new_settings.get("target_roles", settings.target_roles_list)),
        "EXPERIENCE_YEARS": str(
            new_settings.get("experience_years", settings.experience_years)
        ),
        "PREFERRED_LOCATIONS": ",".join(
            new_settings.get("preferred_locations", settings.preferred_locations_list)
        ),
        "MIN_RELEVANCE_SCORE": str(
            new_settings.get("min_relevance_score", settings.min_relevance_score)
        ),
        "USER_FULL_NAME": new_settings.get("user_full_name", settings.user_full_name),
        "EXCLUDED_COMPANIES": ",".join(
            new_settings.get("excluded_companies", settings.excluded_companies_list)
        ),
    }
    # Only overwrite a secret when the client actually sent a value; a blank
    # field means "keep what is already there".
    for field, env_key in _SECRET_KEYS.items():
        value = new_settings.get(field)
        if value:
            updates[env_key] = value

    # Preserve comments and unrelated keys; rewrite only what changed.
    seen = set()
    out_lines: List[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            out_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            out_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    refresh_settings()
    return {"success": True}

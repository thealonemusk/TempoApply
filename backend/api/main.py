"""
FastAPI REST API for TempoApply dashboard.
"""
import asyncio
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import sys
import asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from backend.db.models import Job, get_db, init_db
from backend.config import settings

app = FastAPI(title="TempoApply API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("🚀 TempoApply API started")


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

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
    discovered_at: Optional[datetime]
    applied_at: Optional[datetime]

    class Config:
        from_attributes = True


class ScanRequest(BaseModel):
    platforms: List[str] = ["linkedin", "indeed", "naukri", "instahyre", "company_careers"]
    max_jobs_per_platform: int = 20
    headless: bool = True


class StatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class ManualJobRequest(BaseModel):
    title: str
    company: str
    url: str
    jd_text: str
    location: str = ""
    platform: str = "manual"


# ─── Jobs Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/jobs", response_model=List[JobOut])
def get_jobs(
    status: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all jobs with optional filters."""
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    if platform:
        query = query.filter(Job.platform == platform)
    if min_score is not None:
        query = query.filter(Job.relevance_score >= min_score)
    return query.order_by(Job.relevance_score.desc()).all()


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/manual")
def add_manual_job(req: ManualJobRequest, db: Session = Depends(get_db)):
    """Add a job manually."""
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


@app.delete("/api/jobs/clear")
def clear_discovered_jobs(db: Session = Depends(get_db)):
    """Delete all jobs that are still in 'discovered' or 'scored' status to declutter the dashboard."""
    jobs_to_delete = db.query(Job).filter(Job.status.in_(["discovered", "scored"])).all()
    deleted_count = 0
    for job in jobs_to_delete:
        if job.application:
            db.delete(job.application)
        db.delete(job)
        deleted_count += 1
    db.commit()
    return {"success": True, "deleted_count": deleted_count}


@app.post("/api/jobs/purge-experienced")
def purge_experienced_jobs(db: Session = Depends(get_db)):
    """Purge all existing jobs in DB that exceed 2 years of experience or have senior title keywords."""
    from backend.scrapers.filter_utils import is_job_experience_valid
    all_jobs = db.query(Job).all()
    purged_count = 0
    for job in all_jobs:
        job_dict = {
            "title": job.title,
            "company": job.company,
            "experience_required": job.experience_required,
            "jd_text": job.jd_text,
        }
        is_valid, _ = is_job_experience_valid(job_dict, max_years=settings.experience_years)
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


# ─── Scan Pipeline ───────────────────────────────────────────────────────────

_scan_status = {"running": False, "last_result": None}


@app.post("/api/scan")
async def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    """Trigger a background job scan across platforms."""
    if _scan_status["running"]:
        raise HTTPException(status_code=409, detail="Scan already running")

    async def do_scan():
        _scan_status["running"] = True
        try:
            from backend.pipeline import run_scan_pipeline
            result = await run_scan_pipeline(
                platforms=req.platforms,
                max_jobs_per_platform=req.max_jobs_per_platform,
                headless=req.headless,
            )
            _scan_status["last_result"] = result
        except Exception as e:
            logger.error(f"Scan error: {e}")
            _scan_status["last_result"] = {"error": str(e)}
        finally:
            _scan_status["running"] = False

    background_tasks.add_task(do_scan)
    return {"message": "Scan started", "running": True}


@app.get("/api/scan/status")
def get_scan_status():
    return _scan_status


# ─── Analytics ───────────────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    """Return aggregated application stats."""
    total = db.query(Job).count()
    by_status = {}
    for status in ["discovered", "scored", "tailored", "applied", "interviewing", "rejected", "offer"]:
        by_status[status] = db.query(Job).filter(Job.status == status).count()

    by_platform = {}
    for platform in ["linkedin", "indeed", "naukri", "instahyre", "company_careers", "manual"]:
        by_platform[platform] = db.query(Job).filter(Job.platform == platform).count()

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
        "has_gemini_key": bool(settings.gemini_api_key),
        "has_linkedin": bool(settings.linkedin_email),
        "has_naukri": bool(settings.naukri_email),
        "has_indeed": bool(settings.indeed_email),
        "has_instahyre": bool(settings.instahyre_email),
    }


@app.post("/api/settings")
def update_settings(new_settings: dict):
    """Update settings (writes to .env file)."""
    env_path = Path("config/.env")
    env_path.parent.mkdir(exist_ok=True)

    existing_lines = []
    if env_path.exists():
        existing_lines = env_path.read_text().splitlines()

    updates = {
        "TARGET_ROLES": ",".join(new_settings.get("target_roles", settings.target_roles_list)),
        "EXPERIENCE_YEARS": str(new_settings.get("experience_years", settings.experience_years)),
        "PREFERRED_LOCATIONS": ",".join(new_settings.get("preferred_locations", settings.preferred_locations_list)),
        "MIN_RELEVANCE_SCORE": str(new_settings.get("min_relevance_score", settings.min_relevance_score)),
        "USER_FULL_NAME": new_settings.get("user_full_name", settings.user_full_name),
        "GEMINI_API_KEY": new_settings.get("gemini_api_key", settings.gemini_api_key),
        "LINKEDIN_EMAIL": new_settings.get("linkedin_email", settings.linkedin_email),
        "LINKEDIN_PASSWORD": new_settings.get("linkedin_password", settings.linkedin_password),
        "NAUKRI_EMAIL": new_settings.get("naukri_email", settings.naukri_email),
        "NAUKRI_PASSWORD": new_settings.get("naukri_password", settings.naukri_password),
        "INDEED_EMAIL": new_settings.get("indeed_email", settings.indeed_email),
        "INDEED_PASSWORD": new_settings.get("indeed_password", settings.indeed_password),
        "INSTAHYRE_EMAIL": new_settings.get("instahyre_email", settings.instahyre_email),
        "INSTAHYRE_PASSWORD": new_settings.get("instahyre_password", settings.instahyre_password),
    }

    existing_keys = {}
    for line in existing_lines:
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            existing_keys[k.strip()] = v.strip()

    existing_keys.update(updates)

    new_content = "\n".join(f"{k}={v}" for k, v in existing_keys.items())
    env_path.write_text(new_content)

    return {"success": True}

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

from backend.db.models import Job, Application, BaseResume, get_db, init_db
from backend.config import settings
from backend.ai.latex_parser import parse_tex_file, tex_to_text

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


class ApplicationOut(BaseModel):
    id: str
    job_id: str
    tailored_resume_path: str
    tailored_resume_text: str
    cold_email: str
    linkedin_message: str
    cover_letter: str
    notes: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ScanRequest(BaseModel):
    platforms: List[str] = ["linkedin", "indeed", "naukri", "instahyre"]
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
    """Add a job manually for analysis."""
    from backend.ai.analyzer import analyze_jd
    from backend.ai.latex_parser import parse_tex_file
    from backend.pipeline import get_base_resume_text
    import uuid

    existing = db.query(Job).filter(Job.url == req.url).first()
    if existing:
        raise HTTPException(status_code=409, detail="Job with this URL already exists")

    base_text = get_base_resume_text()
    analysis = analyze_jd(req.jd_text, base_text, req.title)

    job = Job(
        id=str(uuid.uuid4()),
        title=req.title,
        company=req.company,
        platform=req.platform,
        url=req.url,
        location=req.location,
        jd_text=req.jd_text,
        relevance_score=analysis.get("score", 0.0),
        fit_reason=analysis.get("fit_reason", ""),
        missing_skills=json.dumps(analysis.get("missing_skills", [])),
        seniority_level=analysis.get("seniority_level", "mid"),
        is_engineering_role=analysis.get("is_engineering_role", True),
        status="scored",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "score": job.relevance_score, "message": "Job added and analyzed"}


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


# ─── Application Materials ───────────────────────────────────────────────────

@app.post("/api/applications/{job_id}/generate")
def generate_materials(job_id: str, background_tasks: BackgroundTasks):
    """Generate tailored resume + outreach materials for a job."""
    def do_generate():
        from backend.pipeline import generate_application_materials
        generate_application_materials(job_id)

    background_tasks.add_task(do_generate)
    return {"message": "Generating materials...", "job_id": job_id}


@app.get("/api/applications/{job_id}", response_model=ApplicationOut)
def get_application(job_id: str, db: Session = Depends(get_db)):
    app_record = db.query(Application).filter(Application.job_id == job_id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="No application materials yet")
    return app_record


@app.patch("/api/applications/{job_id}/notes")
def update_notes(job_id: str, notes: str, db: Session = Depends(get_db)):
    app_record = db.query(Application).filter(Application.job_id == job_id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found")
    app_record.notes = notes
    db.commit()
    return {"success": True}


# ─── Resume Management ───────────────────────────────────────────────────────

@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a .tex resume file as the base resume."""
    if not file.filename.endswith(".tex"):
        raise HTTPException(status_code=400, detail="Only .tex files are supported")

    save_dir = Path("resumes")
    save_dir.mkdir(exist_ok=True)
    save_path = save_dir / file.filename

    content = await file.read()
    save_path.write_bytes(content)

    tex_text = tex_to_text(content.decode("utf-8", errors="ignore"))

    # Deactivate old resumes
    db.query(BaseResume).update({"is_active": False})

    base = BaseResume(
        filename=file.filename,
        file_path=str(save_path),
        content_text=tex_text,
        is_active=True,
    )
    db.add(base)
    db.commit()
    db.refresh(base)

    # Update settings path
    settings.base_resume_path = str(save_path)

    return {"resume_id": base.id, "filename": file.filename, "preview_chars": len(tex_text)}


@app.get("/api/resume/active")
def get_active_resume(db: Session = Depends(get_db)):
    base = db.query(BaseResume).filter(BaseResume.is_active == True).first()
    if not base:
        return {"resume": None}
    return {
        "resume_id": base.id,
        "filename": base.filename,
        "content_preview": base.content_text[:500],
        "uploaded_at": base.uploaded_at,
    }


@app.get("/api/resume/download/{job_id}")
def download_tailored_resume(job_id: str, db: Session = Depends(get_db)):
    app_record = db.query(Application).filter(Application.job_id == job_id).first()
    if not app_record or not app_record.tailored_resume_path:
        raise HTTPException(status_code=404, detail="Tailored resume not found")
    path = Path(app_record.tailored_resume_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(path), filename=path.name, media_type="application/x-tex")


# ─── Analytics ───────────────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    """Return aggregated application stats."""
    total = db.query(Job).count()
    by_status = {}
    for status in ["discovered", "scored", "tailored", "applied", "interviewing", "rejected", "offer"]:
        by_status[status] = db.query(Job).filter(Job.status == status).count()

    by_platform = {}
    for platform in ["linkedin", "indeed", "naukri", "instahyre", "manual"]:
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

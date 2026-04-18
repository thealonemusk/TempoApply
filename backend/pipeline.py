"""
Job Pipeline Orchestrator — orchestrates the full job discovery, analysis,
resume tailoring, and outreach generation pipeline.
"""
import asyncio
import json
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session

from backend.db.models import Job, Application, BaseResume, SessionLocal
from backend.ai.analyzer import analyze_jd
from backend.ai.resume_tailor import tailor_resume, save_tailored_resume
from backend.ai.cold_email import generate_cold_email, generate_linkedin_message, generate_cover_letter
from backend.ai.latex_parser import parse_tex_file, tex_to_text
from backend.config import settings


def get_base_resume_text() -> str:
    """Load and parse the active base resume from DB or file."""
    db = SessionLocal()
    try:
        base = db.query(BaseResume).filter(BaseResume.is_active == True).first()
        if base and base.content_text:
            return base.content_text
        # Fallback to file
        if Path(settings.base_resume_path).exists():
            return parse_tex_file(settings.base_resume_path)
        return ""
    finally:
        db.close()


def upsert_jobs(jobs: list, db: Session) -> int:
    """Insert new jobs (skip duplicates by URL or Company+Title). Returns count of new jobs."""
    count = 0
    seen_urls = set()
    seen_title_company = set()
    
    frontend_keywords = ['frontend', 'front-end', 'front end', 'react', 'angular', 'vue', 'ui developer', 'user interface']
    
    for job_data in jobs:
        url = job_data.get("url", "")
        title = job_data.get("title", "")
        company = job_data.get("company", "")
        
        # Prevent blanks and intra-batch duplicates by URL
        if not url or url in seen_urls:
            continue
            
        # Filter out frontend roles
        if any(keyword in title.lower() for keyword in frontend_keywords):
            logger.info(f"Skipping frontend role: {title}")
            continue
            
        # Deduplicate globally by (Title, Company)
        tc_key = (title.lower().strip(), company.lower().strip())
        if tc_key in seen_title_company:
            continue
            
        seen_urls.add(url)
        seen_title_company.add(tc_key)
        
        # Prevent database duplicates (by URL)
        existing_url = db.query(Job).filter(Job.url == url).first()
        if existing_url:
            continue
            
        # Prevent database duplicates (by Title + Company)
        existing_tc = db.query(Job).filter(Job.title.ilike(title), Job.company.ilike(company)).first()
        if existing_tc:
            continue
            
        missing_skills = json.dumps(job_data.get("missing_skills", []))
        job = Job(
            title=job_data.get("title", ""),
            company=job_data.get("company", ""),
            platform=job_data.get("platform", ""),
            url=url,
            location=job_data.get("location", ""),
            experience_required=job_data.get("experience_required", ""),
            salary_range=job_data.get("salary_range", ""),
            jd_text=job_data.get("jd_text", ""),
            relevance_score=job_data.get("score", 0.0),
            fit_reason=job_data.get("fit_reason", ""),
            missing_skills=missing_skills,
            seniority_level=job_data.get("seniority_level", ""),
            is_engineering_role=job_data.get("is_engineering_role", True),
            easy_apply=job_data.get("easy_apply", False),
            recruiter_name=job_data.get("recruiter_name", ""),
            recruiter_profile=job_data.get("recruiter_profile", ""),
            status="discovered",
        )
        db.add(job)
        count += 1
    db.commit()
    return count


async def run_scan_pipeline(
    platforms: list = None,
    max_jobs_per_platform: int = 20,
    headless: bool = True,
) -> dict:
    """
    Run the full job discovery pipeline:
    1. Scrape jobs from selected platforms
    2. Analyze each job with Gemini
    3. Store in DB
    Returns summary stats.
    """
    platforms = platforms or ["linkedin", "naukri", "indeed", "instahyre", "company_careers"]
    base_resume_text = ""  # AI matching is disabled

    # Hardcoded roles per user request, bypassing AI to save quotas
    dynamic_roles = ['Software Engineer', 'Backend Engineer', 'Full Stack Developer']

    logger.info(f"Targeting these dynamic AI roles: {dynamic_roles}")

    all_raw_jobs = []

    if "linkedin" in platforms:
        try:
            from backend.scrapers.linkedin import scrape_linkedin_jobs
            logger.info("🔍 Scraping LinkedIn...")
            jobs = await scrape_linkedin_jobs(roles=dynamic_roles, max_jobs=max_jobs_per_platform, headless=headless)
            all_raw_jobs.extend(jobs)
            logger.info(f"LinkedIn: {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"LinkedIn scraping error: {e}")

    if "indeed" in platforms:
        try:
            from backend.scrapers.indeed import scrape_indeed_jobs
            logger.info("🔍 Scraping Indeed...")
            jobs = await scrape_indeed_jobs(roles=dynamic_roles, max_jobs=max_jobs_per_platform, headless=headless)
            all_raw_jobs.extend(jobs)
            logger.info(f"Indeed: {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"Indeed scraping error: {e}")

    if "naukri" in platforms:
        try:
            from backend.scrapers.naukri import scrape_naukri_jobs
            logger.info("🔍 Scraping Naukri...")
            jobs = await scrape_naukri_jobs(roles=dynamic_roles, max_jobs=max_jobs_per_platform, headless=headless)
            all_raw_jobs.extend(jobs)
            logger.info(f"Naukri: {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"Naukri scraping error: {e}")

    if "instahyre" in platforms:
        try:
            from backend.scrapers.instahyre import scrape_instahyre_jobs
            logger.info("🔍 Scraping InstaHyre...")
            jobs = await scrape_instahyre_jobs(roles=dynamic_roles, max_jobs=max_jobs_per_platform, headless=headless)
            all_raw_jobs.extend(jobs)
            logger.info(f"InstaHyre: {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"InstaHyre scraping error: {e}")

    if "company_careers" in platforms:
        try:
            from backend.scrapers.company_careers import scrape_company_career_jobs
            logger.info("🏢 Scraping top Indian company career sites (Greenhouse / Lever / custom)...")
            jobs = await scrape_company_career_jobs(roles=dynamic_roles, max_jobs=max_jobs_per_platform)
            all_raw_jobs.extend(jobs)
            logger.info(f"Company careers: {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"Company careers scraping error: {e}")

    logger.info(f"Total raw jobs found: {len(all_raw_jobs)}")

    # Bypassing AI JD analysis due to quota limits
    analyzed_jobs = []
    for job in all_raw_jobs:
        # Give a default passing score to save them all
        job["score"] = 100
        job["fit_reason"] = "Matched via broad search (AI disabled)"
        analyzed_jobs.append(job)

    # Filter by score (all will pass since score=100)
    qualified = analyzed_jobs
    logger.info(f"Adding {len(qualified)} jobs directly to database...")

    db = SessionLocal()
    try:
        new_count = upsert_jobs(analyzed_jobs, db)
    finally:
        db.close()

    return {
        "total_scraped": len(all_raw_jobs),
        "qualified": len(qualified),
        "new_in_db": new_count,
        "platforms": platforms,
    }


def generate_application_materials(job_id: str) -> dict:
    """
    For a given job, generate:
    - Tailored resume (LaTeX)
    - Cold email
    - LinkedIn message
    - Cover letter
    Store in Application table and return.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"error": "Job not found"}

        base_resume_text = get_base_resume_text()
        base_resume_tex = ""
        if Path(settings.base_resume_path).exists():
            base_resume_tex = Path(settings.base_resume_path).read_text(encoding="utf-8", errors="ignore")

        key_requirements = json.loads(job.missing_skills or "[]")

        # Tailor resume
        tailor_result = tailor_resume(
            jd_text=job.jd_text,
            base_resume_tex=base_resume_tex or base_resume_text,
            job_title=job.title,
            company=job.company,
            key_requirements=key_requirements,
        )
        tailored_path = save_tailored_resume(
            tailor_result["tailored_tex"], job.id, job.company
        )

        # Generate outreach
        cold_email = generate_cold_email(
            job_title=job.title,
            company=job.company,
            jd_text=job.jd_text,
            recruiter_name=job.recruiter_name,
            fit_reason=job.fit_reason,
        )
        linkedin_msg = generate_linkedin_message(
            job_title=job.title,
            company=job.company,
            recruiter_name=job.recruiter_name,
            fit_reason=job.fit_reason,
        )
        cover_letter = generate_cover_letter(
            job_title=job.title,
            company=job.company,
            jd_text=job.jd_text,
            base_resume_text=base_resume_text,
        )

        # Upsert Application record
        app = db.query(Application).filter(Application.job_id == job_id).first()
        if not app:
            app = Application(job_id=job_id)
            db.add(app)

        app.tailored_resume_path = tailored_path
        app.tailored_resume_text = tailor_result["tailored_tex"]
        app.cold_email = cold_email
        app.linkedin_message = linkedin_msg
        app.cover_letter = cover_letter

        job.status = "tailored"
        db.commit()

        logger.info(f"✅ Materials generated for: {job.company} - {job.title}")

        return {
            "job_id": job_id,
            "tailored_resume_path": tailored_path,
            "cold_email": cold_email,
            "linkedin_message": linkedin_msg,
            "cover_letter": cover_letter,
            "changes_summary": tailor_result["changes_summary"],
        }
    except Exception as e:
        logger.error(f"Material generation failed for {job_id}: {e}")
        return {"error": str(e)}
    finally:
        db.close()

"""
Job Pipeline Orchestrator — orchestrates real-time multi-platform job discovery and experience validation.
"""
import asyncio
import json
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session

from backend.db.models import Job, SessionLocal
from backend.scrapers.filter_utils import is_job_experience_valid
from backend.config import settings


def upsert_jobs(jobs: list, db: Session) -> int:
    """Insert new jobs (skip duplicates by URL or Company+Title). Returns count of new jobs."""
    count = 0
    seen_urls = set()
    seen_title_company = set()
    
    frontend_keywords = ['frontend', 'front-end', 'front end', 'react', 'angular', 'vue', 'ui developer', 'user interface']
    max_exp_years = getattr(settings, "experience_years", 2)
    
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
            
        # Enforce hard boundaries on experience (<2 yrs) and title keywords
        is_valid, reason = is_job_experience_valid(job_data, max_years=max_exp_years)
        if not is_valid:
            logger.info(f"🛡️ Hard Filter Excluded [{company} - {title}]: {reason}")
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
    dynamic_roles = ['Software Engineer', 'Backend Engineer', 'Full Stack Developer', 'AI Engineer' , 'Software Developer']

    logger.info(f"Targeting these dynamic AI roles: {dynamic_roles}")

    all_raw_jobs = []
    tasks = []
    platform_names = []

    if "linkedin" in platforms:
        async def run_linkedin():
            from backend.scrapers.linkedin import scrape_linkedin_jobs
            logger.info("🔍 Scraping LinkedIn...")
            return await scrape_linkedin_jobs(roles=dynamic_roles, max_jobs=max_jobs_per_platform, headless=headless)
        tasks.append(run_linkedin())
        platform_names.append("linkedin")

    if "indeed" in platforms:
        async def run_indeed():
            from backend.scrapers.indeed import scrape_indeed_jobs
            logger.info("🔍 Scraping Indeed...")
            return await scrape_indeed_jobs(roles=dynamic_roles, max_jobs=max_jobs_per_platform, headless=headless)
        tasks.append(run_indeed())
        platform_names.append("indeed")

    if "naukri" in platforms:
        async def run_naukri():
            from backend.scrapers.naukri import scrape_naukri_jobs
            logger.info("🔍 Scraping Naukri...")
            return await scrape_naukri_jobs(roles=dynamic_roles, max_jobs=max_jobs_per_platform, headless=headless)
        tasks.append(run_naukri())
        platform_names.append("naukri")

    if "instahyre" in platforms:
        async def run_instahyre():
            from backend.scrapers.instahyre import scrape_instahyre_jobs
            logger.info("🔍 Scraping InstaHyre...")
            return await scrape_instahyre_jobs(roles=dynamic_roles, max_jobs=max_jobs_per_platform, headless=headless)
        tasks.append(run_instahyre())
        platform_names.append("instahyre")

    if "company_careers" in platforms:
        async def run_company_careers():
            from backend.scrapers.company_careers import scrape_company_career_jobs
            logger.info("🏢 Scraping top Indian company career sites (Greenhouse / Lever / custom)...")
            return await scrape_company_career_jobs(roles=dynamic_roles, max_jobs=1000)
        tasks.append(run_company_careers())
        platform_names.append("company_careers")

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(platform_names, results):
            if isinstance(result, Exception):
                logger.error(f"{name} scraping error: {result}")
            elif result:
                all_raw_jobs.extend(result)
                logger.info(f"{name}: {len(result)} jobs")

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

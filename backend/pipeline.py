"""
Job Pipeline Orchestrator — multi-platform job discovery and experience validation.
"""
import asyncio
import json
from loguru import logger
from sqlalchemy.orm import Session

from backend.db.models import Job, SessionLocal
from backend.scrapers.filter_utils import is_job_experience_valid
from backend.scrapers.registry import SCRAPER_REGISTRY, SCRAPER_LABELS, resolve_roles
from backend.config import settings
from backend.platforms import DEFAULT_SCAN_PLATFORMS


def upsert_jobs(jobs: list, db: Session) -> int:
    """Insert new jobs (skip duplicates by URL or Company+Title). Returns count of new jobs."""
    count = 0
    seen_urls = set()
    seen_title_company = set()

    frontend_keywords = [
        "frontend", "front-end", "front end", "react", "angular", "vue",
        "ui developer", "user interface",
    ]
    max_exp_years = getattr(settings, "experience_years", 2)

    excluded = [c.lower() for c in settings.excluded_companies_list if c.strip()]

    for job_data in jobs:
        url = job_data.get("url", "")
        title = job_data.get("title", "")
        company = job_data.get("company", "")

        if excluded and company:
            company_lower = company.lower()
            if any(exc in company_lower for exc in excluded):
                logger.info(f"Skipping excluded company: {company}")
                continue

        if not url or url in seen_urls:
            continue

        if any(keyword in title.lower() for keyword in frontend_keywords):
            logger.info(f"Skipping frontend role: {title}")
            continue

        is_valid, reason = is_job_experience_valid(job_data, max_years=max_exp_years)
        if not is_valid:
            logger.info(f"Hard filter excluded [{company} - {title}]: {reason}")
            continue

        tc_key = (title.lower().strip(), company.lower().strip())
        if tc_key in seen_title_company:
            continue

        seen_urls.add(url)
        seen_title_company.add(tc_key)

        existing_url = db.query(Job).filter(Job.url == url).first()
        if existing_url:
            continue

        existing_tc = db.query(Job).filter(
            Job.title.ilike(title), Job.company.ilike(company)
        ).first()
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
    Run job discovery: scrape selected platforms, apply filters, store in DB.
    """
    platforms = platforms or list(DEFAULT_SCAN_PLATFORMS)
    roles = resolve_roles(settings.target_roles_list)
    logger.info(f"Targeting roles: {roles}")

    all_raw_jobs = []
    tasks = []
    platform_names = []

    for key in platforms:
        scrape_fn = SCRAPER_REGISTRY.get(key)
        if not scrape_fn:
            logger.warning(f"Unknown platform '{key}' — skipping")
            continue

        label = SCRAPER_LABELS.get(key, key)

        async def run_one(fn=scrape_fn, name=key, display=label):
            logger.info(f"Scraping {display}...")
            return await fn(roles=roles, max_jobs=max_jobs_per_platform, headless=headless)

        tasks.append(run_one())
        platform_names.append(key)

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(platform_names, results):
            if isinstance(result, Exception):
                logger.error(f"{name} scraping error: {result}")
            elif result:
                all_raw_jobs.extend(result)
                logger.info(f"{name}: {len(result)} jobs")

    logger.info(f"Total raw jobs found: {len(all_raw_jobs)}")

    analyzed_jobs = []
    for job in all_raw_jobs:
        job["score"] = 100
        job["fit_reason"] = "Matched via broad search"
        analyzed_jobs.append(job)

    db = SessionLocal()
    try:
        new_count = upsert_jobs(analyzed_jobs, db)
    finally:
        db.close()

    return {
        "total_scraped": len(all_raw_jobs),
        "qualified": len(analyzed_jobs),
        "new_in_db": new_count,
        "platforms": platforms,
    }

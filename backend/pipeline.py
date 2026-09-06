"""
Job Pipeline Orchestrator — multi-platform job discovery and experience validation.
"""
import asyncio
import json
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy.orm import Session

import re

from backend.applier.ats import apply_method, detect_ats, is_auto_appliable
from backend.db.models import Job, SessionLocal
from backend.scrapers.filter_utils import (
    is_career_listing_eligible,
    passes_hard_filters,
)
from backend.scrapers.scoring import score_job
from backend.scrapers.registry import SCRAPER_REGISTRY, SCRAPER_LABELS, resolve_discovery_roles
from backend.config import settings
from backend.platforms import DEFAULT_SCAN_PLATFORMS
from backend.job_freshness import JOB_FRESHNESS_HOURS
from backend.runtime.events import RunTracker
from backend.scan_control import clear_stop, should_stop


# The same role often appears twice: once on an aggregator and once on the
# employer's own career site, where the title carries a location or work-mode
# suffix. Normalising both to a common form lets the two collide.
_WORK_MODE = re.compile(r"\((?:remote|hybrid|on-?site)[^)]*\)", re.I)

_LOCATION_SUFFIX = re.compile(
    r"[,\-–]\s*(?:india|bengaluru|bangalore|hyderabad|pune|noida|gurgaon|"
    r"gurugram|chennai|mumbai|kolkata|ahmedabad|remote)(?![a-z]).*$",
    re.I,
)


def normalize_title(title: str) -> str:
    """Collapse a posting title to a comparable form for deduplication."""
    cleaned = _WORK_MODE.sub(" ", title or "")
    cleaned = _LOCATION_SUFFIX.sub("", cleaned)
    return re.sub(r"[^a-z0-9]+", " ", cleaned.lower()).strip()


def _appliable_rank(job_data: dict) -> int:
    """Lower sorts first: prefer the copy auto-apply can actually submit."""
    method = apply_method(
        url=job_data.get("url", ""),
        apply_url=job_data.get("apply_url", ""),
        ats_type=job_data.get("ats_type", ""),
        easy_apply=bool(job_data.get("easy_apply")),
        platform=job_data.get("platform", ""),
    )
    return 0 if is_auto_appliable(method) else 1


def upsert_jobs(jobs: list, db: Session) -> int:
    """Insert new jobs (skip duplicates by URL or Company+Title). Returns count of new jobs."""
    count = 0
    seen_urls = set()
    seen_title_company = set()

    max_exp_years = getattr(settings, "experience_years", 2)
    min_score = getattr(settings, "min_relevance_score", 55)

    excluded = [c.lower() for c in settings.excluded_companies_list if c.strip()]

    # Career-site copies carry a direct ATS link; aggregator copies of the same
    # role do not. Seeing the appliable one first means it claims the dedupe
    # slot and the manual-only twin is dropped.
    jobs = sorted(jobs, key=_appliable_rank)

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

        ok, reason = passes_hard_filters(job_data, max_years=max_exp_years)
        if not ok:
            logger.info(f"Hard filter excluded [{company} - {title}]: {reason}")
            continue

        if job_data.get("platform") == "company_careers":
            eligible, reason = is_career_listing_eligible(job_data)
            if not eligible:
                logger.info(f"Career listing excluded [{company} - {title}]: {reason}")
                continue

        score, fit_reason = score_job(
            job_data,
            target_roles=settings.target_roles_list,
            preferred_locations=settings.preferred_locations_list,
            experience_years=max_exp_years,
        )
        if score < min_score:
            logger.info(f"Below min score ({score} < {min_score}): [{company} - {title}]")
            continue

        job_data["score"] = score
        job_data["fit_reason"] = fit_reason

        tc_key = (normalize_title(title), company.lower().strip())
        if tc_key in seen_title_company:
            continue

        seen_urls.add(url)
        seen_title_company.add(tc_key)

        existing_url = db.query(Job).filter(Job.url == url).first()
        if existing_url:
            continue

        existing_tc = None
        for candidate in db.query(Job).filter(Job.company.ilike(company)).all():
            if normalize_title(candidate.title) == tc_key[0]:
                existing_tc = candidate
                break
        if existing_tc:
            new_apply = job_data.get("apply_url") or ""
            new_ats = job_data.get("ats_type") or detect_ats(new_apply or url)
            already_appliable = is_auto_appliable(
                apply_method(
                    url=existing_tc.url,
                    apply_url=existing_tc.apply_url or "",
                    ats_type=existing_tc.ats_type or "",
                    easy_apply=bool(existing_tc.easy_apply),
                    platform=existing_tc.platform or "",
                )
            )
            if not already_appliable and _appliable_rank(job_data) == 0:
                logger.info(
                    f"Upgrading duplicate to an appliable source: {company} - {title}"
                )
                existing_tc.url = url
                existing_tc.apply_url = new_apply
                existing_tc.ats_type = new_ats
                existing_tc.platform = job_data.get("platform", existing_tc.platform)
                if job_data.get("jd_text"):
                    existing_tc.jd_text = job_data["jd_text"]
                db.commit()
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
            apply_url=job_data.get("apply_url", ""),
            ats_type=(
                job_data.get("ats_type")
                or detect_ats(job_data.get("apply_url", ""))
                or detect_ats(url)
            ),
            status="discovered",
        )
        db.add(job)
        count += 1
    db.commit()
    return count


def purge_visited_jobs(db: Session) -> int:
    """Remove jobs the user opened (visited) that are still in the review queue."""
    visited = db.query(Job).filter(
        Job.visited_at.isnot(None),
        Job.status.in_(["discovered", "scored", "tailored", "ignored"]),
    ).all()
    removed = 0
    for job in visited:
        if job.application:
            db.delete(job.application)
        db.delete(job)
        removed += 1
    if removed:
        db.commit()
    return removed


def purge_stale_discovered_jobs(db: Session, max_age_hours: int = JOB_FRESHNESS_HOURS) -> int:
    """Remove discovered/scored jobs older than max_age_hours."""
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    stale = db.query(Job).filter(
        Job.status.in_(["discovered", "scored"]),
        Job.discovered_at < cutoff,
    ).all()
    removed = 0
    for job in stale:
        if job.application:
            db.delete(job.application)
        db.delete(job)
        removed += 1
    if removed:
        db.commit()
    return removed


async def run_scan_pipeline(
    platforms: list = None,
    max_jobs_per_platform: int = 400,
    headless: bool = True,
) -> dict:
    """
    Run job discovery: scrape selected platforms, apply filters, store in DB.
    """
    platforms = platforms or list(DEFAULT_SCAN_PLATFORMS)
    roles = resolve_discovery_roles(settings.target_roles_list)
    logger.info(f"Targeting roles (discovery): {roles}")
    clear_stop()

    tracker = RunTracker(
        "scan",
        concurrency=len(platforms),
        meta={
            "phase": "scraping",
            "platforms": {p: {"status": "pending", "found": 0, "added": 0} for p in platforms},
            "roles": len(roles),
            "new_in_db": 0,
        },
    )

    def mark(platform: str, **fields) -> None:
        table = dict(tracker.state.meta.get("platforms") or {})
        row = dict(table.get(platform) or {})
        row.update(fields)
        table[platform] = row
        tracker.set_meta(platforms=table)

    all_raw_jobs = []
    tasks = []

    for key in platforms:
        scrape_fn = SCRAPER_REGISTRY.get(key)
        if not scrape_fn:
            logger.warning(f"Unknown platform '{key}' — skipping")
            continue

        label = SCRAPER_LABELS.get(key, key)

        async def run_one(fn=scrape_fn, name=key, display=label):
            if should_stop():
                logger.info(f"Scan stop requested — skipping {display}")
                mark(name, status="skipped")
                return name, []
            logger.info(f"Scraping {display}...")
            mark(name, status="running")
            try:
                jobs = await fn(roles=roles, max_jobs=max_jobs_per_platform, headless=headless)
            except Exception as exc:
                logger.error(f"{name} scraping error: {exc}")
                mark(name, status="error", error=str(exc)[:200])
                return name, []
            return name, jobs or []

        tasks.append(run_one())

    db = SessionLocal()
    stale_removed = 0
    visited_removed = 0
    new_count = 0
    try:
        visited_removed = purge_visited_jobs(db)
        if visited_removed:
            logger.info(f"Removed {visited_removed} previously visited jobs")

        if tasks:
            for finished in asyncio.as_completed(tasks):
                try:
                    name, result = await finished
                except Exception as exc:
                    logger.error(f"Platform scraping error: {exc}")
                    continue
                if not result:
                    logger.info(f"{name}: 0 jobs")
                    mark(name, status="done", found=0, added=0)
                    continue
                all_raw_jobs.extend(result)
                added = upsert_jobs(result, db)
                new_count += added
                mark(name, status="done", found=len(result), added=added)
                tracker.set_meta(new_in_db=new_count)
                logger.info(f"{name}: {len(result)} jobs ({added} new in db)")

        logger.info(f"Total raw jobs found: {len(all_raw_jobs)}")

        stale_removed = purge_stale_discovered_jobs(db, max_age_hours=JOB_FRESHNESS_HOURS)
        if stale_removed:
            logger.info(f"Purged {stale_removed} stale discovered jobs (>{JOB_FRESHNESS_HOURS}h)")
    except Exception as exc:
        logger.exception("Scan pipeline crashed")
        tracker.finish("error", message=str(exc), error="scan_crashed")
        raise
    finally:
        db.close()

    result = {
        "total_scraped": len(all_raw_jobs),
        "qualified": len(all_raw_jobs),
        "new_in_db": new_count,
        "visited_removed": visited_removed,
        "stale_removed": stale_removed,
        "platforms": platforms,
    }
    stopped = should_stop()
    tracker.set_meta(phase="done", **result)
    tracker.finish(
        "stopped" if stopped else "done",
        message=(
            "Stopped by user"
            if stopped
            else f"{new_count} new job{'' if new_count == 1 else 's'} "
            f"from {len(all_raw_jobs)} scraped"
        ),
    )
    return result

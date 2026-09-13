"""
Permanent record of every job the scanner has ever surfaced.

The `jobs` table is a working queue, not a history: `purge_visited_jobs` and
`purge_stale_discovered_jobs` delete rows out of it on every scan. Dedup that
consults only that table therefore forgets, and the next scan happily re-adds
the jobs it just removed - the user sees the same posting they already opened,
scan after scan.

This ledger outlives those purges. It answers one question - "have we already
dealt with this posting?" - and separates two cases:

  * BLOCKING statuses are decisions: the user opened it, applied to it,
    dismissed it, or it aged out of the queue. Never show it again.
  * Non-blocking statuses ("seen", "filtered", "discovered") are observability.
    Hard filters re-run cheaply on every scan, so a job rejected by a filter is
    recorded with its reason but is free to come back if the filters change.
"""
from __future__ import annotations

import hashlib
import re
import urllib.parse
from typing import Dict, Iterable, Optional, Set, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from backend.db.models import Job, SeenJob

# Decisions. A job whose ledger status is one of these is never re-inserted.
BLOCKING_STATUSES = {
    "visited",
    "dismissed",
    "applied",
    "interviewing",
    "rejected",
    "offer",
    "expired",
}

# Query parameters that identify the referrer rather than the posting. Stripping
# them lets the same job arrive from two searches and dedupe to one row. Only
# these are removed - parameters like Greenhouse's gh_jid carry the job id
# itself, so dropping the query string wholesale would break dedup, not help it.
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "trk", "trackingid", "refid", "position", "pagenum", "originaltoken",
    "src", "source", "ref", "referrer", "gh_src", "lever-source",
    "lever-origin", "gclid", "fbclid", "eburl", "originalsubdomain",
}

_WS_RE = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    """Canonical form of a posting URL, for stable dedup across searches."""
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parts = urllib.parse.urlsplit(raw)
    except ValueError:
        return raw.lower()

    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/") or "/"

    kept = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS
    ]
    query = urllib.parse.urlencode(sorted(kept))

    # Fragment dropped: it never identifies a different posting.
    return urllib.parse.urlunsplit(
        (parts.scheme.lower() or "https", host, path, query, "")
    )


def _digest(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def url_key(url: str) -> str:
    normalized = normalize_url(url)
    return _digest(normalized) if normalized else ""


def tc_key(title: str, company: str) -> str:
    """Secondary key: the same job listed under two URLs (or two platforms)."""
    t = _WS_RE.sub(" ", (title or "").strip().lower())
    c = _WS_RE.sub(" ", (company or "").strip().lower())
    if not t or not c:
        return ""
    return _digest(f"{t}|{c}")


def load_blocklist(db: Session) -> Tuple[Set[str], Set[str]]:
    """Every blocking key, in one query.

    Returned as sets so a scan checks thousands of candidates in memory instead
    of issuing a SELECT per job.
    """
    rows = (
        db.query(SeenJob.url_key, SeenJob.tc_key)
        .filter(SeenJob.status.in_(BLOCKING_STATUSES))
        .all()
    )
    urls = {row[0] for row in rows if row[0]}
    tcs = {row[1] for row in rows if row[1]}
    return urls, tcs


def record(
    db: Session,
    job_data: Dict,
    status: str = "seen",
    reason: str = "",
    commit: bool = False,
) -> Optional[SeenJob]:
    """Insert or refresh the ledger row for a scraped job dict.

    An existing blocking status is never downgraded - a scan re-seeing a job
    the user already applied to must not reset it to "discovered".
    """
    url = job_data.get("url", "")
    key = url_key(url)
    if not key:
        return None

    title = job_data.get("title", "") or ""
    company = job_data.get("company", "") or ""

    row = db.query(SeenJob).filter(SeenJob.url_key == key).first()
    if row is None:
        row = SeenJob(
            url_key=key,
            url=url,
            tc_key=tc_key(title, company),
            title=title,
            company=company,
            platform=job_data.get("platform", "") or "",
            status=status,
            reason=reason[:500],
            times_seen=1,
        )
        db.add(row)
    else:
        row.times_seen = (row.times_seen or 0) + 1
        if not row.tc_key:
            row.tc_key = tc_key(title, company)
        if row.status not in BLOCKING_STATUSES:
            row.status = status
            row.reason = reason[:500]

    if commit:
        db.commit()
    return row


def mark(
    db: Session,
    url: str,
    status: str,
    reason: str = "",
    title: str = "",
    company: str = "",
    platform: str = "",
    commit: bool = False,
) -> Optional[SeenJob]:
    """Set a ledger status, creating the row if the job was never recorded."""
    key = url_key(url)
    if not key:
        return None

    row = db.query(SeenJob).filter(SeenJob.url_key == key).first()
    if row is None:
        row = SeenJob(
            url_key=key,
            url=url,
            tc_key=tc_key(title, company),
            title=title,
            company=company,
            platform=platform,
            times_seen=1,
        )
        db.add(row)
    row.status = status
    row.reason = reason[:500]
    if commit:
        db.commit()
    return row


def mark_jobs(db: Session, jobs: Iterable[Job], status: str, reason: str = "") -> int:
    """Mark a batch of Job rows - call this before deleting them."""
    count = 0
    for job in jobs:
        mark(
            db,
            url=job.url,
            status=status,
            reason=reason,
            title=job.title or "",
            company=job.company or "",
            platform=job.platform or "",
        )
        count += 1
    return count


def unblock(db: Session, url: str) -> bool:
    """Escape hatch: let a job be rediscovered after it was marked."""
    key = url_key(url)
    if not key:
        return False
    row = db.query(SeenJob).filter(SeenJob.url_key == key).first()
    if row is None:
        return False
    row.status = "seen"
    row.reason = "manually unblocked"
    db.commit()
    return True


def stats(db: Session) -> Dict:
    from sqlalchemy import func as sa_func

    rows = (
        db.query(SeenJob.status, sa_func.count(SeenJob.url_key))
        .group_by(SeenJob.status)
        .all()
    )
    by_status = {status: count for status, count in rows}
    return {
        "total": sum(by_status.values()),
        "blocking": sum(v for k, v in by_status.items() if k in BLOCKING_STATUSES),
        "by_status": by_status,
    }


# Status a job's lifecycle maps to when seeding the ledger from existing rows.
_JOB_STATUS_TO_LEDGER = {
    "applied": "applied",
    "interviewing": "interviewing",
    "rejected": "rejected",
    "offer": "offer",
    "ignored": "dismissed",
}


def backfill_from_jobs(db: Session) -> int:
    """Seed the ledger from the existing jobs table.

    Runs once, when the ledger is empty. Without it, every job already applied
    to or visited before this table existed would look brand new on the first
    scan after the upgrade.
    """
    if db.query(SeenJob).first() is not None:
        return 0

    jobs = db.query(Job).all()
    seeded = 0
    for job in jobs:
        status = _JOB_STATUS_TO_LEDGER.get(job.status or "")
        if status is None:
            status = "visited" if job.visited_at else "discovered"
        if mark(
            db,
            url=job.url,
            status=status,
            reason="backfilled from jobs table",
            title=job.title or "",
            company=job.company or "",
            platform=job.platform or "",
        ):
            seeded += 1
    if seeded:
        db.commit()
        logger.info(f"Seen ledger: backfilled {seeded} rows from the jobs table")
    return seeded

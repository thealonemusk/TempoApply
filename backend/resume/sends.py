"""
The send log: which resume each application carried, and what came back.

Keyword coverage says how well a resume matches a posting. It does not say
whether anyone called. This is the only number in the tailoring pipeline that
measures the goal, and it needs no model — only the record of what was sent,
joined to the status the user sets on the dashboard.

A callback is a job moved to `interviewing` or `offer`. An application with
no reply after `NO_REPLY_DAYS` counts as a no; one younger than that is still
pending and is left out of the rate rather than counted as a failure.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from backend.db.models import Job, ResumeSend

CALLBACK = {"interviewing", "offer"}
NO_REPLY_DAYS = 21
# Below this many settled applications a bucket's rate is noise.
MIN_SAMPLE = 20


def _report_for(pdf: Path) -> Dict[str, Any]:
    # The uploaded copy lives in <job dir>/upload/, the report in <job dir>/.
    folder = pdf.parent.parent if pdf.parent.name == "upload" else pdf.parent
    report = folder / "report.json"
    if not report.is_file():
        return {}
    try:
        return json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def record(db: Session, job_id: str, path: Path, *, channel: str, tailored: bool) -> None:
    """Log the resume attached to this job. Never raises: logging must not block a fill."""
    try:
        path = Path(path)
        report = _report_for(path) if tailored else {}
        cov = (report.get("coverage") or {}).get("required") or {}
        glance = (report.get("first_glance") or {}).get("required") or {}
        row = db.get(ResumeSend, job_id) or ResumeSend(job_id=job_id)
        job = db.get(Job, job_id)
        if job is not None:
            row.company, row.title = job.company, job.title
            row.status, row.applied_at = job.status, job.applied_at
        row.sent_at = datetime.utcnow()
        row.channel = channel
        row.variant = "tailored" if tailored else "default"
        row.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        row.path = str(path)
        row.llm_used = bool(report.get("llm_used"))
        row.coverage = (cov.get("after") or {}).get("score")
        row.first_glance = (glance.get("after") or {}).get("score")
        row.reordered = len(report.get("reordered") or []) + len(report.get("skills_reordered") or [])
        row.reworded = int(report.get("model_rewrites") or 0)
        db.merge(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning(f"Could not record resume send for {job_id}: {exc}")


def _outcome(send: ResumeSend, job: Optional[Job], now: datetime) -> str:
    """
    callback | rejected | no_reply | pending | not_submitted

    The live job wins when it still exists; a deleted job's outcome comes from
    the copy kept on the send row.
    """
    status = ((job.status if job is not None else send.status) or "").lower()
    applied_at = job.applied_at if job is not None else send.applied_at
    if status in CALLBACK:
        return "callback"
    if status == "rejected":
        return "rejected"
    if status != "applied":
        return "not_submitted"
    since = applied_at or send.sent_at
    if since and now - since < timedelta(days=NO_REPLY_DAYS):
        return "pending"
    return "no_reply"


def _bucket_stats(outcomes: List[str]) -> Dict[str, Any]:
    counts = {k: outcomes.count(k) for k in ("callback", "rejected", "no_reply", "pending")}
    settled = counts["callback"] + counts["rejected"] + counts["no_reply"]
    return {
        **counts,
        "sent": sum(counts.values()),
        "settled": settled,
        "rate": round(100.0 * counts["callback"] / settled, 1) if settled else None,
        "enough_data": settled >= MIN_SAMPLE,
    }


def _glance_bucket(score: Optional[float]) -> str:
    if score is None:
        return "untailored"
    if score < 40:
        return "<40"
    if score < 70:
        return "40-70"
    return "70+"


def callback_stats(db: Session, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Callback rate overall and split by how the resume was prepared."""
    now = now or datetime.utcnow()
    rows = db.query(ResumeSend, Job).outerjoin(Job, Job.id == ResumeSend.job_id).all()

    groups: Dict[str, Dict[str, List[str]]] = {
        "variant": {}, "llm_used": {}, "first_glance": {},
    }
    overall: List[str] = []
    for send, job in rows:
        outcome = _outcome(send, job, now)
        if outcome == "not_submitted":
            continue
        overall.append(outcome)
        groups["variant"].setdefault(send.variant or "default", []).append(outcome)
        groups["llm_used"].setdefault("reworded" if send.llm_used else "not reworded", []).append(outcome)
        groups["first_glance"].setdefault(_glance_bucket(send.first_glance), []).append(outcome)

    return {
        "overall": _bucket_stats(overall),
        "by": {
            name: {key: _bucket_stats(vals) for key, vals in sorted(buckets.items())}
            for name, buckets in groups.items()
        },
        "rules": {
            "callback": sorted(CALLBACK),
            "no_reply_after_days": NO_REPLY_DAYS,
            "min_sample": MIN_SAMPLE,
        },
    }

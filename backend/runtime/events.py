"""
Shared run-progress contract for the scan and apply pipelines.

One in-process broker holds the live state of at most one run per kind
("apply", "scan") and fans every mutation out to SSE subscribers. Both
pipelines publish through `RunTracker`; the API exposes snapshots at
/api/{kind}/run and a live stream at /api/{kind}/stream.

Frames pushed to subscribers are JSON-serialisable dicts:

    {"type": "run",  "data": <run snapshot without jobs>}
    {"type": "job",  "data": <job progress incl. steps>}
    {"type": "step", "data": {"job_id": ..., "step": <step>}}
    {"type": "end",  "data": <full run snapshot>}
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from loguru import logger

RunKind = Literal["apply", "scan"]

# Terminal per-job outcomes. Kept in sync with Job.apply_status in the DB.
JOB_STATES = ("queued", "running", "applied", "needs_review", "failed", "skipped")
TERMINAL_JOB_STATES = ("applied", "needs_review", "failed", "skipped")

RUN_STATUSES = ("idle", "running", "stopping", "stopped", "done", "error")

# Per-job step history is capped so a pathological wizard cannot grow unbounded.
MAX_STEPS_PER_JOB = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Step:
    """One observable action inside a job attempt."""

    ts: str
    kind: str  # navigate | detect | signin | upload | fill | next | submit | confirm | error | info
    detail: str = ""
    ok: Optional[bool] = None


@dataclass
class JobProgress:
    job_id: str
    title: str = ""
    company: str = ""
    url: str = ""
    ats: str = ""
    state: str = "queued"
    message: str = ""
    screenshot: str = ""  # path relative to the project root, if one was captured
    final_url: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    steps: List[Step] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunState:
    run_id: str
    kind: str
    status: str = "idle"
    concurrency: int = 1
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    message: str = ""
    error: str = ""
    # Free-form per-kind detail: platform counters for scan, profile info for apply.
    meta: Dict[str, Any] = field(default_factory=dict)
    jobs: Dict[str, JobProgress] = field(default_factory=dict)

    @property
    def totals(self) -> Dict[str, int]:
        counts = {state: 0 for state in JOB_STATES}
        for job in self.jobs.values():
            counts[job.state] = counts.get(job.state, 0) + 1
        counts["total"] = len(self.jobs)
        counts["done"] = sum(counts.get(s, 0) for s in TERMINAL_JOB_STATES)
        return counts

    def header(self) -> Dict[str, Any]:
        """Run-level snapshot without the (potentially large) job list."""
        return {
            "run_id": self.run_id,
            "kind": self.kind,
            "status": self.status,
            "concurrency": self.concurrency,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "message": self.message,
            "error": self.error,
            "meta": self.meta,
            "totals": self.totals,
            "running": self.status in ("running", "stopping"),
        }

    def snapshot(self) -> Dict[str, Any]:
        data = self.header()
        data["jobs"] = [job.to_dict() for job in self.jobs.values()]
        return data


class _Broker:
    """Fan-out to SSE subscribers, plus the last run state per kind."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._runs: Dict[str, RunState] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── state ────────────────────────────────────────────────────────────
    def current(self, kind: RunKind) -> RunState:
        run = self._runs.get(kind)
        if run is None:
            run = RunState(run_id="", kind=kind, status="idle")
            self._runs[kind] = run
        return run

    def set_current(self, run: RunState) -> None:
        self._runs[run.kind] = run

    # ── pub/sub ──────────────────────────────────────────────────────────
    def subscribe(self, kind: RunKind) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=512)
        self._subscribers.setdefault(kind, []).append(queue)
        return queue

    def unsubscribe(self, kind: RunKind, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(kind) or []
        if queue in subs:
            subs.remove(queue)

    def remember_loop(self) -> None:
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def publish(self, kind: RunKind, frame: Dict[str, Any]) -> None:
        """Push a frame to every subscriber. Safe to call from the loop thread."""
        for queue in list(self._subscribers.get(kind) or []):
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                # A stalled client must never slow the pipeline down.
                logger.debug(f"Dropping {kind} frame for a slow SSE subscriber")

    def publish_threadsafe(self, kind: RunKind, frame: Dict[str, Any]) -> None:
        """Publish from a worker thread (scrapers use asyncio.to_thread)."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self.publish, kind, frame)


BROKER = _Broker()


class RunTracker:
    """Write-side handle a pipeline uses to report progress."""

    def __init__(self, kind: RunKind, concurrency: int = 1, meta: Optional[Dict[str, Any]] = None):
        self.kind: RunKind = kind
        self.state = RunState(
            run_id=uuid.uuid4().hex[:12],
            kind=kind,
            status="running",
            concurrency=concurrency,
            started_at=_now(),
            meta=dict(meta or {}),
        )
        BROKER.remember_loop()
        BROKER.set_current(self.state)
        self._emit_run()

    # ── run level ────────────────────────────────────────────────────────
    def _emit_run(self) -> None:
        BROKER.publish(self.kind, {"type": "run", "data": self.state.header()})

    def set_status(self, status: str, message: str = "") -> None:
        self.state.status = status
        if message:
            self.state.message = message
        self._emit_run()

    def set_meta(self, **values: Any) -> None:
        self.state.meta.update(values)
        self._emit_run()

    def finish(self, status: str = "done", message: str = "", error: str = "") -> Dict[str, Any]:
        self.state.status = status
        self.state.finished_at = _now()
        if message:
            self.state.message = message
        if error:
            self.state.error = error
        snapshot = self.state.snapshot()
        BROKER.publish(self.kind, {"type": "end", "data": snapshot})
        return snapshot

    # ── job level ────────────────────────────────────────────────────────
    def add_job(
        self,
        job_id: str,
        title: str = "",
        company: str = "",
        url: str = "",
        ats: str = "",
        state: str = "queued",
    ) -> JobProgress:
        job = JobProgress(
            job_id=job_id, title=title, company=company, url=url, ats=ats, state=state
        )
        self.state.jobs[job_id] = job
        self._emit_job(job)
        return job

    def _emit_job(self, job: JobProgress) -> None:
        BROKER.publish(self.kind, {"type": "job", "data": job.to_dict()})
        self._emit_run()

    def job(self, job_id: str) -> Optional[JobProgress]:
        return self.state.jobs.get(job_id)

    def start_job(self, job_id: str, ats: str = "") -> None:
        job = self.state.jobs.get(job_id)
        if not job:
            return
        job.state = "running"
        job.started_at = _now()
        if ats:
            job.ats = ats
        self._emit_job(job)

    def step(
        self,
        job_id: str,
        kind: str,
        detail: str = "",
        ok: Optional[bool] = None,
    ) -> None:
        job = self.state.jobs.get(job_id)
        if not job:
            return
        entry = Step(ts=_now(), kind=kind, detail=detail[:300], ok=ok)
        job.steps.append(entry)
        if len(job.steps) > MAX_STEPS_PER_JOB:
            del job.steps[: len(job.steps) - MAX_STEPS_PER_JOB]
        BROKER.publish(
            self.kind, {"type": "step", "data": {"job_id": job_id, "step": asdict(entry)}}
        )

    def finish_job(
        self,
        job_id: str,
        state: str,
        message: str = "",
        ats: str = "",
        screenshot: str = "",
        final_url: str = "",
    ) -> None:
        job = self.state.jobs.get(job_id)
        if not job:
            return
        job.state = state
        job.message = message
        job.finished_at = _now()
        if ats:
            job.ats = ats
        if screenshot:
            job.screenshot = screenshot
        if final_url:
            job.final_url = final_url
        self._emit_job(job)


def current_snapshot(kind: RunKind) -> Dict[str, Any]:
    return BROKER.current(kind).snapshot()

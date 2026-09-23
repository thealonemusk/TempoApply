"""
Tailor a LaTeX resume to one job description and compile it to PDF.

The sequence, and why each step is where it is:

  1. parse    — split the .tex into a frozen document and editable prose spans
  2. analyse  — turn the JD into requirements (deterministic + optional LLM)
  3. rank     — score every bullet against those requirements, deterministically
  4. rewrite  — the model rewords bullets; it sees plain text and returns plain text
  5. guard    — reject any rewrite introducing a fact the master does not contain
  6. render   — splice accepted rewrites back in, escape, harden against ligatures
  7. compile  — Tectonic
  8. fit      — while it spills past one page, drop the lowest-ranked bullet and rebuild
  9. report   — before/after keyword coverage, what changed, what was cut

Steps 3 and 5 are the ones that make the output trustworthy: the model never
decides what is true or what matters, only how a sentence reads.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from loguru import logger

from backend.resume import compile as rc
from backend.resume import guard as guard_mod
from backend.resume import jd as jd_mod
from backend.resume import llm, match, texdoc

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESUMES_DIR = PROJECT_ROOT / "resumes"
TAILORED_DIR = RESUMES_DIR / "tailored"
DEFAULT_MASTER = RESUMES_DIR / "master_resume.tex"

MAX_TRIM_ROUNDS = 12

SYSTEM = (
    "You are a resume editor. You rewrite a candidate's existing bullet points so they "
    "speak the vocabulary of a specific job description. You never invent experience. "
    "Everything you write must be supported by the bullet you were given. Answer with JSON only."
)

REWRITE_TEMPLATE = """Rewrite this candidate's resume bullets for the job below.

=== THE JOB ===
Title: {job_title}
Company: {company}
Seniority: {seniority}
Domain: {domain}
Required: {required}
Preferred: {preferred}
Responsibilities: {responsibilities}
The employer's own keywords: {keywords}

=== THE CANDIDATE'S BULLETS (these are the only facts you may use) ===
{bullets}

=== WHAT TO DO ===
For each bullet, decide whether re-wording it would make its relevance to this job clearer.
Return only the bullets you actually changed.

HARD RULES — a violation gets the rewrite discarded automatically:
- Never name a technology, tool, company, product or certification that is not already in
  that candidate's bullets. If the job wants Kafka and the bullet says MQTT, you write about
  MQTT; you may describe it as event-driven messaging, but you may not write "Kafka".
- Never change a number, and never add one. "45 production changes" stays 45.
- Never claim seniority, team size, or duration that is not stated.
- Keep each rewrite within roughly 15% of the original length. This resume must stay one page.

WHAT GOOD LOOKS LIKE:
- Lead with the outcome, then the method.
- Use the employer's phrasing wherever it genuinely describes what the candidate did.
  If they say "distributed systems" and the bullet describes a device fleet across regions,
  that phrasing is fair. If they say "Kubernetes" and the bullet never mentions it, it is not.
- Surface work that is already implied but unnamed. Debugging a memory leak IS debugging and
  performance tuning; say so if the job asks for it.
- Keep concrete metrics; they are the most persuasive part of any bullet.

{summary_rule}

Return JSON:
{{
  "rewrites": {{"<slot id>": "<rewritten sentence>"}},
  "notes": "<one sentence on the angle you took>"
}}"""

SUMMARY_STRICT = (
    "The summary bullet (if present) follows the same rules as every other bullet."
)
SUMMARY_TRANSFERABLE = (
    "For the summary bullet only, you may name the candidate's closest genuine equivalent to a "
    "requirement they do not have, provided you frame it as what they did do and never claim the "
    "missing thing itself. Example: \"event-driven messaging at fleet scale (MQTT/MQTTS)\" is "
    "acceptable against a Kafka requirement; \"Kafka experience\" is not."
)


@dataclass
class TailorResult:
    ok: bool
    pdf_path: str = ""
    tex_path: str = ""
    report_path: str = ""
    report: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "pdf_path": self.pdf_path,
            "tex_path": self.tex_path,
            "report_path": self.report_path,
            "report": self.report,
            "error": self.error,
        }


def master_path(configured: str = "") -> Path:
    if configured:
        p = Path(configured)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.is_file():
            return p
    if DEFAULT_MASTER.is_file():
        return DEFAULT_MASTER
    candidates = sorted(RESUMES_DIR.glob("*.tex"))
    return candidates[0] if candidates else DEFAULT_MASTER


def has_master(configured: str = "") -> bool:
    return master_path(configured).is_file()


def _slug(text: str) -> str:
    out = re.sub(r"[^\w\s-]", "", text or "").strip()
    return re.sub(r"[\s-]+", "_", out)[:40] or "job"


def output_dir(company: str, job_id: str) -> Path:
    return TAILORED_DIR / f"{_slug(company)}_{(job_id or 'adhoc')[:8]}"


def tailored_pdf(job_id: str) -> Optional[Path]:
    """
    The tailored PDF produced for this job, or None.

    A PDF older than the master .tex is ignored: it was built from a resume
    that has since been edited, and would send an employer the old version.
    """
    if not job_id or not TAILORED_DIR.is_dir():
        return None
    pdf = next(TAILORED_DIR.glob(f"*_{job_id[:8]}/resume.pdf"), None)
    if pdf is None:
        return None
    master = master_path()
    if master.is_file() and pdf.stat().st_mtime < master.stat().st_mtime:
        logger.info(f"Ignoring stale tailored resume {pdf} — the master .tex is newer")
        return None
    return pdf


def tailored_upload(job_id: str, filename: str = "") -> Optional[Path]:
    """
    The tailored PDF under the name an employer should see.

    Every tailored file is called `resume.pdf`, and an upload carries its file
    name, so a copy is kept beside it under the default resume's name. It stays
    inside `resumes/tailored/<sub>/` — a PDF directly in `resumes/` would be
    picked up by `ApplicantProfile.resume_file()` as the default for every job.
    """
    pdf = tailored_pdf(job_id)
    if pdf is None:
        return None
    name = Path(filename).stem + ".pdf" if filename else pdf.name
    if name == pdf.name:
        return pdf
    named = pdf.parent / name
    if not named.is_file() or named.stat().st_mtime < pdf.stat().st_mtime:
        shutil.copyfile(pdf, named)
    return named


def _bullet_block(slots: Sequence, ranks: Dict[str, float]) -> str:
    lines = []
    for slot in slots:
        where = " / ".join(x for x in (slot.section, slot.entry) if x)
        lines.append(f"[{slot.id}] ({where}) relevance={ranks.get(slot.id, 0)}\n{slot.text}")
    return "\n\n".join(lines)


def _propose_rewrites(
    doc: texdoc.TexDoc,
    spec: jd_mod.JobSpec,
    ranks: Dict[str, float],
    transferable: bool,
) -> tuple[Dict[str, str], str]:
    """Ask the model for reworded bullets. Returns (rewrites, notes)."""
    editable = doc.editable_slots
    if not editable:
        return {}, "no editable bullets found"
    if not llm.is_available():
        # Bullets are spliced back at their original offsets, so nothing is
        # re-ordered here — without a key the run still compiles, audits, trims
        # to one page and reports the keyword gap, but the wording is untouched.
        return {}, "no API key — compiled, audited and trimmed, but not reworded"

    prompt = REWRITE_TEMPLATE.format(
        job_title=spec.job_title or "(not given)",
        company=spec.company or "(not given)",
        seniority=spec.seniority or "(not given)",
        domain=spec.domain or "(not given)",
        required=", ".join(spec.all_required()[:20]) or "(none extracted)",
        preferred=", ".join(spec.preferred[:12]) or "(none)",
        responsibilities="; ".join(spec.responsibilities[:8]) or "(none)",
        keywords=", ".join(spec.ats_keywords[:20]) or "(none)",
        bullets=_bullet_block(editable, ranks),
        summary_rule=SUMMARY_TRANSFERABLE if transferable else SUMMARY_STRICT,
    )
    try:
        data = llm.ask_json(SYSTEM, prompt)
    except Exception as exc:  # noqa: BLE001 - tailoring still works without rewrites
        logger.warning(f"Rewrite call failed: {exc}")
        return {}, f"rewrite unavailable ({exc})"

    raw = data.get("rewrites") or {}
    valid_ids = {s.id for s in editable}
    rewrites = {
        str(k): " ".join(str(v).split())
        for k, v in raw.items()
        if str(k) in valid_ids and str(v).strip()
    }
    return rewrites, str(data.get("notes") or "")


def _fit_to_one_page(
    doc: texdoc.TexDoc,
    edits: Dict[str, str],
    ranks: Dict[str, float],
    out_pdf: Path,
    tectonic: str,
    max_pages: int,
) -> tuple[rc.Audit, List[str], str]:
    """
    Compile, and while the document spills over `max_pages`, drop the least
    relevant bullet and rebuild. Returns (audit, dropped slot ids, final source).
    """
    dropped: List[str] = []
    # Lowest relevance first — that is the order sacrifices are made in.
    droppable = sorted(
        (s for s in doc.slots if s.droppable),
        key=lambda s: (ranks.get(s.id, 0.0), -s.start),
    )

    # Emptying an itemize environment is a LaTeX error ("perhaps a missing
    # \item"), so every role and project must keep at least one bullet. Losing a
    # job's last line would also read as a gap in the work history.
    groups: Dict[tuple, List[str]] = {}
    for slot in doc.slots:
        if slot.droppable:
            groups.setdefault((slot.section, slot.entry), []).append(slot.id)

    def can_drop(slot_id: str) -> bool:
        for members in groups.values():
            if slot_id in members:
                remaining = [m for m in members if m not in dropped]
                return len(remaining) > 1
        return True

    # Re-inject *every* editable bullet, not only the reworded ones. Unchanged
    # text is spliced back identically except that `escape()` breaks its
    # ligatures, which is what stops "traffic" reaching the PDF as "traﬃc".
    all_edits = {slot.id: edits.get(slot.id, slot.text) for slot in doc.editable_slots}

    for _ in range(MAX_TRIM_ROUNDS + 1):
        source = texdoc.harden(doc.render(edits=all_edits, drop=dropped))
        audit = rc.compile_tex(source, out_pdf, tectonic=tectonic)
        if audit.pages <= max_pages:
            return audit, dropped, source

        nxt = next(
            (s.id for s in droppable if s.id not in dropped and can_drop(s.id)),
            None,
        )
        if nxt is None:
            logger.warning("Nothing left to drop; resume still exceeds the page limit")
            return audit, dropped, source
        logger.info(f"{audit.pages} pages — dropping lowest-relevance bullet {nxt}")
        dropped.append(nxt)

    source = texdoc.harden(doc.render(edits=edits, drop=dropped))
    audit = rc.compile_tex(source, out_pdf, tectonic=tectonic)
    return audit, dropped, source


def tailor(
    jd_text: str,
    *,
    job_title: str = "",
    company: str = "",
    job_id: str = "",
    master: str = "",
    tectonic: str = "",
    transferable: bool = True,
    max_pages: int = 1,
    use_llm: bool = True,
) -> TailorResult:
    """Produce a job-specific PDF from the master LaTeX resume."""
    src_path = master_path(master)
    if not src_path.is_file():
        return TailorResult(ok=False, error=f"No master resume. Expected a .tex at {DEFAULT_MASTER}")
    if not rc.is_available(tectonic):
        return TailorResult(ok=False, error="Tectonic is not installed (tools/tectonic.exe)")

    doc = texdoc.parse_file(src_path)
    if not doc.slots:
        return TailorResult(
            ok=False,
            error="No editable bullets found in the .tex — the parser did not recognise its macros",
        )

    spec = jd_mod.analyse(jd_text, title=job_title, company=company, use_llm=use_llm)
    required = spec.all_required()
    ranks = match.rank_slots(doc.slots, required, spec.preferred)

    rewrites, notes = _propose_rewrites(doc, spec, ranks, transferable)

    master_plain = texdoc.plain_text(doc)
    gate = guard_mod.Guard(master_plain)
    accepted, rejected = gate.filter(rewrites)
    if rejected:
        for item in rejected:
            logger.info(f"Guard rejected {item['slot']}: {item['reason']}")

    out_dir = output_dir(company or spec.company, job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "resume.pdf"

    try:
        audit, dropped, final_source = _fit_to_one_page(
            doc, accepted, ranks, pdf_path, tectonic, max_pages
        )
    except rc.CompileError as exc:
        return TailorResult(ok=False, error=f"LaTeX failed: {exc}")

    tex_path = out_dir / "resume.tex"
    tex_path.write_text(final_source, encoding="utf-8")

    # The comparison the user actually cares about, measured on extracted PDF
    # text rather than on the source, because that is what an ATS reads.
    try:
        base_edits = {slot.id: slot.text for slot in doc.editable_slots}
        base_audit = rc.compile_tex(
            texdoc.harden(doc.render(edits=base_edits)), out_dir / "base.pdf", tectonic=tectonic
        )
        before_text = base_audit.text
    except rc.CompileError:
        before_text = master_plain

    report = {
        "job": spec.as_dict(),
        "coverage": match.gap_report(before_text, audit.text, required, spec.preferred),
        "changed": [
            {
                "slot": slot_id,
                "section": (doc.slot(slot_id).section if doc.slot(slot_id) else ""),
                "entry": (doc.slot(slot_id).entry if doc.slot(slot_id) else ""),
                "before": (doc.slot(slot_id).text if doc.slot(slot_id) else ""),
                "after": text,
            }
            for slot_id, text in accepted.items()
        ],
        "rejected": rejected,
        "dropped": [
            {
                "slot": slot_id,
                "text": (doc.slot(slot_id).text if doc.slot(slot_id) else ""),
                "why": "did not fit on one page",
            }
            for slot_id in dropped
        ],
        "pdf": {
            "pages": audit.pages,
            "characters": audit.chars,
            "problems": audit.problems(),
            "fonts": audit.fonts,
        },
        "notes": notes,
        "slots_total": len(doc.slots),
        "slots_editable": len(doc.editable_slots),
    }

    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return TailorResult(
        ok=True,
        pdf_path=str(pdf_path),
        tex_path=str(tex_path),
        report_path=str(report_path),
        report=report,
    )

"""
Job description -> structured requirements.

Deterministic first: the technology vocabulary in `match.py` finds what the
posting concretely asks for, with no API call and no variance. An LLM pass then
adds what a keyword list cannot judge — which requirements are hard versus
nice-to-have, the real seniority, and the responsibilities phrased as duties
rather than nouns.

The LLM pass is optional by design. Without a key the analysis degrades to the
deterministic half rather than failing, so the gap report still works offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from loguru import logger

from backend.resume import llm, match

SYSTEM = (
    "You extract hiring requirements from job descriptions. "
    "You never invent requirements that are not stated or clearly implied. "
    "Answer with JSON only."
)

TEMPLATE = """Read this job description and extract what the employer is screening for.

JOB TITLE: {title}
COMPANY: {company}

JOB DESCRIPTION:
{jd}

Return JSON with exactly these keys:
{{
  "job_title": "the role title as the employer writes it",
  "seniority": "intern | entry | mid | senior | staff",
  "required": ["hard requirements - technologies, skills, qualifications the posting treats as mandatory"],
  "preferred": ["nice-to-have or bonus items"],
  "responsibilities": ["what the person will actually do, each a short phrase"],
  "ats_keywords": ["exact terms and phrases an ATS would scan this resume for, in the employer's own wording"],
  "domain": "one short phrase for the problem domain, e.g. payments infrastructure"
}}

Rules:
- Use the employer's own vocabulary. If they say "RESTful services" do not normalise it to "REST".
- "required" must be things the posting states, not things you assume for the role.
- Keep each list to at most 15 entries, most important first."""


@dataclass
class JobSpec:
    """What a posting screens for."""

    job_title: str = ""
    company: str = ""
    seniority: str = ""
    domain: str = ""
    required: List[str] = field(default_factory=list)
    preferred: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    ats_keywords: List[str] = field(default_factory=list)
    tech: List[str] = field(default_factory=list)      # deterministic vocabulary hits
    source: str = "deterministic"                       # deterministic | llm

    def all_required(self) -> List[str]:
        """Requirements plus the vocabulary hits, de-duplicated, order preserved."""
        out: List[str] = []
        seen = set()
        for term in list(self.required) + list(self.tech):
            key = term.lower().strip()
            if key and key not in seen:
                seen.add(key)
                out.append(term)
        return out

    def as_dict(self) -> Dict[str, Any]:
        return {
            "job_title": self.job_title,
            "company": self.company,
            "seniority": self.seniority,
            "domain": self.domain,
            "required": self.required,
            "preferred": self.preferred,
            "responsibilities": self.responsibilities,
            "ats_keywords": self.ats_keywords,
            "tech": self.tech,
            "source": self.source,
        }


def _clean_list(value: Any, limit: int = 15) -> List[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = str(item).strip()
        if text and len(text) < 120:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def analyse(
    jd_text: str,
    title: str = "",
    company: str = "",
    *,
    use_llm: bool = True,
) -> JobSpec:
    """Structure a job description. Falls back to keyword extraction on any failure."""
    jd_text = (jd_text or "").strip()
    spec = JobSpec(
        job_title=title,
        company=company,
        tech=match.find_tech(jd_text),
        required=match.find_tech(jd_text),
        ats_keywords=match.keywords(jd_text, limit=25),
    )
    if not jd_text:
        return spec

    if not (use_llm and llm.is_available()):
        logger.info("JD analysed deterministically (no LLM key configured)")
        return spec

    try:
        data = llm.ask_json(
            SYSTEM,
            TEMPLATE.format(title=title or "(not given)", company=company or "(not given)",
                            jd=jd_text[:12000]),
        )
    except Exception as exc:  # noqa: BLE001 - degrade, never fail the run
        logger.warning(f"JD LLM analysis failed, using keywords only: {exc}")
        return spec

    spec.job_title = str(data.get("job_title") or title or "").strip()
    spec.seniority = str(data.get("seniority") or "").strip()
    spec.domain = str(data.get("domain") or "").strip()
    spec.required = _clean_list(data.get("required")) or spec.required
    spec.preferred = _clean_list(data.get("preferred"))
    spec.responsibilities = _clean_list(data.get("responsibilities"))
    spec.ats_keywords = _clean_list(data.get("ats_keywords"), limit=25) or spec.ats_keywords
    spec.source = "llm"
    return spec

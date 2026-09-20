"""
Repeating sections: work experience, education, websites.

Workday's "My Experience" step is not a flat form. Work Experience, Education
and Websites each start *empty* behind an Add button, and once expanded they
repeat — `workExperience-1`, `workExperience-2`, each with its own Job Title,
Company, From, To and Description. A flat label -> value resolver cannot answer
those: "Company" means something different in entry 1 than in entry 2.

So the scraper tags every field with the entry it belongs to, and this module
answers per entry, reading down the profile's experience/education lists.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from backend.applier.profile import ApplicantProfile, Education, Experience

# How many entries of each kind the profile can fill.
KINDS = ("experience", "education", "website")


def _norm(text: str) -> str:
    text = (text or "").lower().replace("*", " ")
    text = re.sub(r"[^a-z0-9\s/+.-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _has_word(text: str, *words: str) -> bool:
    """
    Whole-word containment.

    A plain `"to" in label` is the repo's recurring bug class: it fires on
    "Total Compensation" and "Custom", so a pay question reads as the end date
    of a job and comes back blank.
    """
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text)
        for word in words
    )


def _split_month_year(value: str) -> Tuple[str, str]:
    """'01/2025' -> ('01', '2025'); 'Present' -> ('', '')."""
    raw = (value or "").strip()
    m = re.match(r"^(\d{1,2})\s*[/-]\s*(\d{4})$", raw)
    if m:
        return m.group(1).zfill(2), m.group(2)
    m = re.match(r"^(\d{4})\s*[/-]\s*(\d{1,2})$", raw)
    if m:
        return m.group(2).zfill(2), m.group(1)
    m = re.search(r"\b(\d{4})\b", raw)
    if m:
        return "", m.group(1)
    return "", ""


def _is_current(exp: Experience) -> bool:
    return _norm(exp.end_date) in {"present", "current", "now", ""}


def needed_counts(profile: ApplicantProfile) -> dict:
    """How many entries of each repeating section this profile would fill."""
    websites = [w for w in (profile.linkedin, profile.github, profile.portfolio) if w]
    return {
        "experience": len([e for e in profile.experience if e.title or e.company]),
        "education": len([e for e in profile.education if e.school or e.degree]),
        "website": len(websites),
    }


def _websites(profile: ApplicantProfile) -> List[str]:
    return [w for w in (profile.linkedin, profile.github, profile.portfolio) if w]


def _experience_value(exp: Experience, label: str) -> str:
    n = _norm(label)
    from_ctx = _has_word(n, "from", "start")
    to_ctx = _has_word(n, "to", "end", "through")

    # Workday splits dates into separate Month and Year inputs.
    if "month" in n or "year" in n:
        source = exp.end_date if to_ctx else exp.start_date
        if to_ctx and _is_current(exp):
            return ""
        month, year = _split_month_year(source)
        return month if "month" in n else year

    # Spellings seen across tenants for the "this is my current job" checkbox.
    # Deliberately does not include "current employer" — that labels the
    # company name box on some tenants, and answering it "Yes" loses the name.
    if any(x in n for x in ("currently work", "currently working", "work here",
                            "current position", "present position", "still work")):
        return "Yes" if _is_current(exp) else "No"
    # Description is checked before title: Workday labels the free-text box
    # "Role Description", which would otherwise match the title needles.
    if any(x in n for x in ("description", "responsibilities", "duties", "achievements", "details")):
        return exp.description
    if any(x in n for x in ("job title", "title", "position", "role")):
        return exp.title
    if any(x in n for x in ("company", "employer", "organization", "organisation")):
        return exp.company
    if "location" in n or "city" in n:
        return exp.location
    if from_ctx:
        return exp.start_date
    if to_ctx:
        return "" if _is_current(exp) else exp.end_date
    return ""


def _website_value(profile: ApplicantProfile, label: str, index: int) -> str:
    """
    Which link this box wants.

    Position is the fallback, not the rule. Workday numbers its Websites
    panels, but a tenant that writes "Please provide your LinkedIn profile"
    has named the link it wants, and panel 2 is GitHub only by accident of
    ordering — so a named question is answered by name first.
    """
    n = _norm(label)
    for needle, value in (
        ("linkedin", profile.linkedin),
        ("github", profile.github),
        ("git hub", profile.github),
        ("portfolio", profile.portfolio),
        ("personal website", profile.portfolio),
        ("personal site", profile.portfolio),
    ):
        if needle in n and value:
            return value

    sites = _websites(profile)
    if index > len(sites):
        return ""
    return sites[index - 1]


def _education_value(edu: Education, label: str, gpa: str) -> str:
    n = _norm(label)
    from_ctx = _has_word(n, "from", "start") or "first year" in n
    to_ctx = _has_word(n, "to", "end") or "last year" in n or "graduat" in n

    if "year" in n and not any(x in n for x in ("field", "study")):
        return edu.end_year if to_ctx else (edu.start_year if from_ctx else edu.end_year)
    if any(x in n for x in ("school", "university", "college", "institution")):
        return edu.school
    if any(x in n for x in ("field of study", "major", "discipline", "specialization", "specialisation")):
        return edu.major
    if "degree" in n or "qualification" in n:
        return edu.degree
    if "gpa" in n or "cgpa" in n or "grade" in n or "result" in n:
        return gpa
    if from_ctx:
        return edu.start_year
    if to_ctx:
        return edu.end_year
    return ""


def section_value(
    profile: ApplicantProfile,
    kind: str,
    index: int,
    label: str,
) -> str:
    """Answer `label` for entry `index` (1-based) of a repeating section."""
    if index < 1:
        index = 1

    if kind == "experience":
        usable = [e for e in profile.experience if e.title or e.company]
        if index > len(usable):
            return ""
        return _experience_value(usable[index - 1], label)

    if kind == "education":
        usable = [e for e in profile.education if e.school or e.degree]
        if index > len(usable):
            return ""
        answers = profile.custom_answers or {}
        gpa = str(answers.get("gpa") or answers.get("cgpa") or "")
        return _education_value(usable[index - 1], label, gpa)

    if kind == "website":
        return _website_value(profile, label, index)

    return ""


def skill_list(profile: ApplicantProfile, limit: int = 10) -> List[str]:
    """
    Individual skills for a multi-select widget.

    The profile's skills string is a long CV line; a Workday skill picker only
    accepts entries from its own taxonomy, so the compound ones
    ("TLS/Certificate Rotation") are dropped and the plain technology names
    kept, most important first.
    """
    raw = [s.strip() for s in (profile.skills or "").split(",")]
    out: List[str] = []
    for item in raw:
        if not item or len(item) > 28:
            continue
        # "AWS (EC2, S3)" -> "AWS"; a slashed pair is not a taxonomy entry.
        item = re.sub(r"\s*\(.*$", "", item).strip()
        if not item or "/" in item:
            continue
        if item.lower() in {s.lower() for s in out}:
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return out

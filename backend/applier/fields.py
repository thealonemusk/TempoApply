"""Map form labels to applicant profile values. Deterministic — no LLM."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from backend.applier.profile import ApplicantProfile, Education

# Longer aliases first so "first name" wins over "name".
FIELD_ALIASES: List[Tuple[str, Tuple[str, ...]]] = [
    ("first_name", ("first name", "firstname", "given name", "legal first", "preferred first")),
    ("last_name", ("last name", "lastname", "surname", "family name", "legal last")),
    ("full_name", ("full name", "legal name", "applicant name", "your name", "candidate name")),
    ("email", ("email address", "e-mail", "email")),
    ("phone", ("phone number", "mobile number", "telephone", "mobile phone", "cell phone", "phone", "mobile", "cell")),
    ("phone_country", ("phone country", "country code", "dialing code")),
    ("linkedin", ("linkedin url", "linkedin profile link", "linkedin profile", "linkedin")),
    ("github", ("github url", "github profile", "github", "git hub")),
    ("portfolio", ("portfolio url", "personal website", "personal url", "website url", "portfolio", "website")),
    ("salary_expectation", (
        "salary expectation", "expected salary", "expected ctc", "current ctc",
        "current/last base salary", "current last base salary", "base salary",
        "total cash entitlement", "total cash", "compensation", "desired salary", "pay expectation",
    )),
    ("notice_period", ("notice period", "notice")),
    ("address_line1", ("address line 1", "street address", "address 1", "home address")),
    ("address_line2", ("address line 2", "apartment", "suite", "unit")),
    ("city", ("city", "town")),
    ("state", ("state / province", "state/province", "province", "region", "state")),
    ("postal_code", ("postal code", "zip code", "zip/postal", "pincode", "pin code", "zip")),
    ("country", ("country / region", "country/region", "country")),
    ("location", ("current location", "location", "city, state", "where are you based")),
    ("current_company", ("current company", "current employer", "company name", "employer", "organization")),
    ("current_title", ("current title", "job title", "headline", "most recent title")),
    ("years_experience", ("years of experience", "years experience", "total experience", "experience (years)")),
    ("earliest_start", ("earliest start", "start date", "available from", "availability date", "when can you start", "date available")),
    ("cover_letter", ("cover letter", "additional information", "additional details", "comments", "message to hiring")),
    ("school", ("school name", "university", "college", "institution")),
    ("degree", ("degree", "qualification")),
    ("major", ("major", "field of study", "discipline", "specialization")),
    ("how_heard", ("how did you hear", "where did you hear", "how did you find", "referral source", "source")),
    ("gpa", ("cgpa", "gpa", "grade point")),
]

YES_TRUE = {"yes", "true", "y", "1"}

QUESTION_RULES: List[Tuple[Tuple[str, ...], str]] = [
    (("how did you hear", "where did you hear", "how did you find this", "source of hire", "where did you see the vacancy"), "how_heard"),
    (("country of residence", "current country of residence", "current country"), "country"),
    (("employment agreement", "post-employment", "restrictive covenant"), "no"),
    (("previously worked", "have you previously worked", "consulted for gitlab", "consulted for"), "no"),
    (("valid passport",), "yes"),
    (("legally authorized to work in india", "authorized to work in india", "eligible to work in india", "authorized to work in the country"), "yes"),
    (("legally authorized to work in india", "authorized to work in india", "eligible to work in india"), "yes"),
    (("legally authorized to work in the united states", "authorized to work in the us", "authorized to work in the u.s"), "work_auth_us"),
    (("legally authorized", "authorized to work", "eligible to work", "right to work", "work authorization"), "work_auth"),
    (("require sponsorship", "need sponsorship", "visa sponsorship", "require visa", "future sponsorship", "immigration sponsorship"), "sponsorship"),
    (("over 18", "18 years of age", "at least 18"), "yes"),
    (("willing to relocate", "open to relocate", "can you relocate", "ready to relocate"), "relocate"),
    (("attached a custom cover letter", "have you attached a custom cover"), "no"),
    (("willing to work remotely", "remote work"), "yes"),
    (("current (or most recent) employer", "most recent employer", "last employer you have been", "name and location of the last employer", "who is your current"), "current_company"),
    (("previously applied", "have you applied"), "no"),
    (("related to anyone", "know anyone who works", "employee referral name"), "no"),
    (("non-compete", "noncompete"), "no"),
    (("conflict of interest",), "no"),
    (("gender identity", "gender", "sex"), "gender"),
    (("hispanic", "latino", "ethnicity", "race", "racial"), "ethnicity"),
    (("veteran status", "protected veteran", "veteran"), "veteran"),
    (("disability", "disabled"), "disability"),
    (("pronoun",), "decline"),
    (("i identify as",), "decline"),
    (("i certify", "information is true", "accurate and complete", "acknowledge that"), "yes"),
    (("privacy policy", "terms and conditions", "terms of use", "i agree", "i consent", "consent to"), "yes"),
    (("receive updates", "marketing emails", "sms notifications", "text messages"), "no"),
    (("export control", "deemed export", "itir", "itar"), "no"),
]


def _norm(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("*", " ")
    text = re.sub(r"\(optional\)", " ", text)
    text = re.sub(r"[^a-z0-9\s+/.-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _bool_text(value: bool) -> str:
    return "Yes" if value else "No"


def _education(profile: ApplicantProfile) -> Education:
    for row in profile.education:
        if row.school or row.degree:
            return row
    return Education()


def value_for_key(profile: ApplicantProfile, key: str, job_title: str = "", company: str = "") -> str:
    edu = _education(profile)
    mapping = {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "full_name": profile.full_name,
        "email": profile.email,
        "phone": profile.phone_e164() or profile.phone,
        "phone_national": profile.phone_national(),
        "phone_country": profile.phone_country,
        "linkedin": profile.linkedin,
        "github": profile.github,
        "portfolio": profile.portfolio or profile.github,
        "address_line1": profile.address_line1,
        "address_line2": profile.address_line2,
        "city": profile.city,
        "state": profile.state,
        "postal_code": profile.postal_code,
        "country": profile.country,
        "location": profile.location_string(),
        "current_company": profile.current_company,
        "current_title": profile.current_title,
        "years_experience": profile.years_experience,
        "notice_period": profile.notice_period,
        "earliest_start": profile.earliest_start,
        "salary_expectation": profile.salary_expectation,
        "cover_letter": profile.cover_letter(job_title, company),
        "school": edu.school,
        "degree": edu.degree,
        "major": edu.major,
        "gpa": (profile.custom_answers or {}).get("gpa") or (profile.custom_answers or {}).get("cgpa") or "",
        "how_heard": profile.how_heard,
        "gender": profile.gender,
        "ethnicity": profile.ethnicity,
        "veteran": profile.veteran,
        "disability": profile.disability,
        "yes": "Yes",
        "no": "No",
        "decline": "Decline to self-identify",
        "work_auth": _bool_text(profile.authorized_to_work),
        "work_auth_us": "No" if profile.require_sponsorship else _bool_text(profile.authorized_to_work),
        "sponsorship": _bool_text(profile.require_sponsorship),
        "relocate": "Yes",
    }
    return mapping.get(key, "") or ""


def custom_answer(profile: ApplicantProfile, label: str) -> str:
    n = _norm(label)
    for needle, answer in (profile.custom_answers or {}).items():
        if _norm(needle) and _norm(needle) in n:
            return str(answer)
    return ""


def match_field_key(label: str) -> Optional[str]:
    n = _norm(label)
    if not n:
        return None
    for key, aliases in FIELD_ALIASES:
        for alias in aliases:
            if alias == n or n.startswith(alias + " ") or f" {alias}" in f" {n}":
                if key == "full_name" and ("first" in n or "last" in n):
                    continue
                if key == "country" and "phone" in n:
                    return "phone_country"
                return key
    return None


def match_question_key(label: str) -> Optional[str]:
    n = _norm(label)
    for needles, key in QUESTION_RULES:
        if any(needle in n for needle in needles):
            return key
    return None


def resolve_value(profile: ApplicantProfile, label: str, job_title: str = "", company: str = "") -> str:
    label_n = _norm(label)
    title_n = _norm(job_title)
    relocate_q = any(x in label_n for x in ("relocate", "ready to relocate", "open to relocate", "willing to relocate"))
    if relocate_q or ("based in" in label_n and "chennai" in label_n):
        if "chennai" in label_n or "chennai" in title_n:
            return "No"
        if relocate_q:
            return "Yes"
    custom = custom_answer(profile, label)
    if custom:
        return custom
    key = match_field_key(label)
    if key:
        return value_for_key(profile, key, job_title, company)
    qkey = match_question_key(label)
    if qkey:
        return value_for_key(profile, qkey, job_title, company)
    return ""


def pick_option(options: List[str], desired: str) -> Optional[str]:
    if not options or not desired:
        return None
    d = _norm(desired)
    cleaned = [(opt, _norm(opt)) for opt in options if _norm(opt) and _norm(opt) not in {"select", "select an option", "please select", "-"}]
    if not cleaned:
        return None
    for opt, n in cleaned:
        if n == d:
            return opt
    for opt, n in cleaned:
        if d in n or n in d:
            return opt
    decline_needles = ("decline", "do not want", "don't wish", "prefer not", "not listed", "i do not")
    if any(x in d for x in ("decline", "not want", "prefer not")):
        for opt, n in cleaned:
            if any(x in n for x in decline_needles):
                return opt
    if d in YES_TRUE or d == "yes":
        for opt, n in cleaned:
            if n in {"yes", "y", "true"} or n.startswith("yes"):
                return opt
    if d in {"no", "false", "n"}:
        for opt, n in cleaned:
            if n in {"no", "n", "false"} or n.startswith("no "):
                return opt
    # Prefer a non-placeholder option only when there is exactly one real choice.
    if len(cleaned) == 1:
        return cleaned[0][0]
    return None


def is_consent_label(label: str) -> bool:
    n = _norm(label)
    return any(x in n for x in (
        "i agree", "i consent", "i certify", "i acknowledge", "acknowledge",
        "acknowledge/confirm", "privacy policy", "terms and conditions",
        "terms of use", "accurate", "truthful",
    ))


def is_skip_field(label: str, name: str, autocomplete: str) -> bool:
    blob = _norm(f"{label} {name} {autocomplete}")
    if any(x in blob for x in ("honeypot", "website_url", "leave this blank", "do not fill")):
        return True
    if name.startswith("utf8") or name in {"_method", "authenticity_token"}:
        return True
    return False

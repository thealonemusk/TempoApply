"""
Filter utilities — text parsing and strict experience/title boundary checks.
Enforces hard limits to ensure only entry-level / early-career (<= 2 years exp) jobs are retained.
"""

import re
from typing import Optional, Tuple

# Keywords in job titles that indicate non-entry-level or senior positions
EXCLUDED_TITLE_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "staff", "principal", "manager",
    "director", "head", "architect", "sde 2", "sde-2", "sde2", "sde 3", "sde-3",
    "sde3", "sde ii", "sde-ii", "sde iii", "sde-iii", "level 2", "level 3", "l2", "l3",
    "expert", "vp", "vice president", "chief", "tech lead", "team lead",
    "consultant", "specialist",
]

# Patterns in job titles indicating level II/III or 2/3 (non-entry)
EXCLUDED_TITLE_REGEXES = [
    r'\b(?:ii|iii|iv|v)\b',
    r'(?<!\d)[-_\s](?:2|3|4|5)(?!(?:\s*\+|\s*(?:years?|yrs?|yr|y)\b|\s+to\s+\d))',
]

# Hard cap: no JD or listing may ask for more than 2 years of experience.
MAX_JD_EXPERIENCE_YEARS = 2.0

INTERN_PATTERN = re.compile(r'\bintern(?:s|ship)?\b', re.IGNORECASE)

ENTRY_TITLE_SIGNALS = [
    "new grad", "new-grad", "university", "graduate", "fresher", "entry level",
    "entry-level", "associate", "junior", "software engineer i",
    "sde i", "sde-1", "sde 1", "developer i", "engineer i", "engineer 1",
    "0-1 year", "0-2 year", "1-2 year", "upto 2", "up to 2", "early career",
]

GENERIC_ENGINEER_TITLES = [
    "software engineer", "software developer", "backend engineer", "backend developer",
    "full stack", "fullstack", "full-stack", "sde", "platform engineer",
    "devops engineer", "machine learning engineer", "ai engineer", "ml engineer",
]

# e.g. "6+yrs", "9+ years", "5 to 7 years", "6-10 years" in titles
TITLE_EXPERIENCE_PATTERN = re.compile(
    r'(?:'
    r'(?:\d+(?:\.\d+)?)\s*\+\s*(?:yrs?|years?|yr|exp)?'
    r'|(?:\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(?:\d+(?:\.\d+)?)\s*(?:yrs?|years?|yr|y)?'
    r'|\b(?:\d+(?:\.\d+)?)\s*(?:yrs?|years?)\s*(?:of\s+)?(?:exp|experience)\b'
    r')',
    re.IGNORECASE,
)


def _experience_exceeds_cap(min_y: float, max_y: float, cap: float = MAX_JD_EXPERIENCE_YEARS) -> bool:
    """True if the stated range asks for more than `cap` years."""
    return min_y > cap or max_y > cap


def parse_experience_years(text: str) -> Optional[Tuple[float, float]]:
    """
    Extract (min_years, max_years) from text snippets like:
    - "3-5 Yrs", "0-2 years", "1 to 3 yrs"
    - "3+ years", "Minimum 3 years", "at least 4 yrs"
    - "2 yrs", "5 years"
    Returns None if no experience numbers are detected.
    """
    if not text:
        return None

    clean_text = text.lower().strip()

    range_match = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr|y)\b',
        clean_text,
    )
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    plus_match = re.search(
        r'(?:minimum|min\.?|at least)?\s*(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?|yr|y)?',
        clean_text,
    )
    if plus_match:
        min_y = float(plus_match.group(1))
        return min_y, min_y + 3.0

    min_phrase_match = re.search(
        r'(?:minimum|min\.?|at least)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr|y)?',
        clean_text,
    )
    if min_phrase_match:
        min_y = float(min_phrase_match.group(1))
        return min_y, min_y + 2.0

    standalone_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr|y)', clean_text)
    if standalone_match:
        val = float(standalone_match.group(1))
        return val, val

    return None


def is_job_experience_valid(job_data: dict, max_years: float = MAX_JD_EXPERIENCE_YEARS) -> Tuple[bool, str]:
    """
    Reject jobs whose title, listing, or JD asks for more than 2 years of experience.

    Returns:
        (is_valid: bool, reason: str)
    """
    cap = min(max_years, MAX_JD_EXPERIENCE_YEARS)
    title = job_data.get("title", "").strip()
    title_lower = title.lower()
    jd_text = job_data.get("jd_text", "").strip()

    if title and INTERN_PATTERN.search(title):
        return False, f"Title mentions intern/internship: '{title}'"

    for keyword in EXCLUDED_TITLE_KEYWORDS:
        if keyword in title_lower:
            return False, f"Title contains senior/excluded keyword: '{keyword}' in '{title}'"

    for pattern in EXCLUDED_TITLE_REGEXES:
        if re.search(pattern, title_lower):
            return False, f"Title matches excluded level pattern: '{pattern}' in '{title}'"

    if TITLE_EXPERIENCE_PATTERN.search(title):
        title_exp = parse_experience_years(title)
        if title_exp:
            min_y, max_y = title_exp
            if _experience_exceeds_cap(min_y, max_y, cap):
                return False, (
                    f"Title requires more than {cap} years of experience "
                    f"(parsed {min_y}-{max_y}): '{title}'"
                )
        else:
            return False, f"Title contains experience requirement pattern: '{title}'"

    exp_str = job_data.get("experience_required", "").strip()
    if exp_str:
        exp_range = parse_experience_years(exp_str)
        if exp_range:
            min_y, max_y = exp_range
            if _experience_exceeds_cap(min_y, max_y, cap):
                return False, (
                    f"Experience field ({exp_str}) requires more than {cap} years "
                    f"(parsed {min_y}-{max_y})"
                )

    if jd_text:
        jd_exp_matches = re.finditer(
            r'(?:requir(?:e|ed|es)|must have|minimum|at least|\+|\b)\s*'
            r'(\d+(?:\.\d+)?)\s*(?:\+|\-|to)?\s*(\d+(?:\.\d+)?)?\s*'
            r'(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)?',
            jd_text.lower(),
        )
        for match in jd_exp_matches:
            val1 = float(match.group(1)) if match.group(1) else 0.0
            val2 = float(match.group(2)) if match.group(2) else 0.0
            phrase = match.group(0)

            if "+" in phrase:
                max_y = val1 + 3.0
            elif val2 > 0:
                max_y = val2
            else:
                max_y = val1

            if _experience_exceeds_cap(val1, max_y, cap):
                return False, (
                    f"JD requires more than {cap} years of experience: '{phrase.strip()}'"
                )

    return True, "Passed experience boundaries check"


def is_career_listing_eligible(job_data: dict) -> Tuple[bool, str]:
    """
    Stricter gate for direct career-site listings that often lack metadata.
    Generic engineer titles need entry-level signals or a usable JD.
    """
    title_lower = job_data.get("title", "").lower()
    jd_text = (job_data.get("jd_text") or "").strip()

    if len(jd_text) >= 200:
        return True, "Has detailed JD"

    if any(sig in title_lower for sig in ENTRY_TITLE_SIGNALS):
        return True, "Entry-level signals in title"

    if any(g in title_lower for g in GENERIC_ENGINEER_TITLES):
        return False, (
            "Generic career-site listing without entry-level signals or JD: "
            f"'{job_data.get('title', '')}'"
        )

    return True, "Specific non-generic title"


def is_pure_frontend_role(title: str) -> bool:
    """Skip frontend-only roles; keep full-stack / backend roles that mention React."""
    t = title.lower()
    frontend_only = [
        "frontend developer", "front-end developer", "front end developer",
        "frontend engineer", "ui developer", "react developer", "angular developer",
        "vue developer", "reactjs developer", "react.js developer",
        ".net react developer",
    ]
    if any(p in t for p in frontend_only):
        return True
    if "full stack" in t or "fullstack" in t or "full-stack" in t or "backend" in t:
        return False
    if re.search(r"\breact\b", t) and "full" not in t and "stack" not in t:
        return True
    return False

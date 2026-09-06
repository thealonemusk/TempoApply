"""
Filter utilities — text parsing and strict experience/title/location checks.
Hard limits: <= 2 years experience, no frontend-only roles, India-only locations.
"""

import re
from typing import Optional, Tuple

EXCLUDED_TITLE_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "staff", "principal", "manager",
    "director", "head", "architect", "sde 2", "sde-2", "sde2", "sde 3", "sde-3",
    "sde3", "sde ii", "sde-ii", "sde iii", "sde-iii", "level 2", "level 3", "level 4",
    "l2", "l3", "l4", "l5",
    "expert", "vp", "vice president", "chief", "tech lead", "team lead",
    "consultant", "specialist", "advanced software", "advanced engineer",
    "advanced developer",
]

EXCLUDED_TITLE_REGEXES = [
    r'\b(?:ii|iii|iv|v)(?:new)?\b',
    r'\bl[2-7]\b',
    r'(?<!\d)[-_\s](?:2|3|4|5)(?!(?:\s*\+|\s*(?:years?|yrs?|yr|y)\b|\s+to\s+\d))',
]

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

YEAR_TOKEN = r'(?:years?|yrs?|yr)\b'

RANGE_YEARS_RE = re.compile(
    rf'(\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)\s*{YEAR_TOKEN}',
    re.IGNORECASE,
)
PLUS_YEARS_RE = re.compile(
    rf'(\d+(?:\.\d+)?)\s*(?:\+|plus)\s*{YEAR_TOKEN}',
    re.IGNORECASE,
)
MIN_YEARS_RE = re.compile(
    rf'(?:minimum|min\.?|at least|atleast|more than|over)\s*(\d+(?:\.\d+)?)\s*{YEAR_TOKEN}',
    re.IGNORECASE,
)
SOLO_YEARS_RE = re.compile(
    rf'(\d+(?:\.\d+)?)\s*{YEAR_TOKEN}(?:\s*(?:\+|plus))?(?:\s+(?:of\s+)?(?:relevant\s+)?(?:professional\s+)?(?:industry\s+)?(?:software\s+)?(?:work\s+)?(?:experience|exp))?',
    re.IGNORECASE,
)
EXP_PREFIX_RE = re.compile(
    rf'(?:experience|exp(?:erience)?)\s*[:\-]?\s*(\d+(?:\.\d+)?)(?:\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?))?(?:\s*{YEAR_TOKEN})?',
    re.IGNORECASE,
)
JD_EXP_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:-|to|–|—)?\s*(\d+(?:\.\d+)?)?\s*(?:\+|plus)?\s*(?:years?|yrs?|yr)\b',
    re.IGNORECASE,
)
JD_HISTORY_BEFORE_RE = re.compile(
    r'(?:for|past|last|next|over the(?: past| last)?|in the last|since|founded|'
    r'nearly|almost|about|previous|prior|spanning)\s+$',
    re.IGNORECASE,
)
MIN_JD_CHARS = 80

INDIA_PLATFORMS = {"naukri", "instahyre", "indeed"}
INDIA_MARKERS = (
    "india", "bharat", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai",
    "gurugram", "gurgaon", "noida", "delhi", "new delhi", "ncr", "chennai",
    "kolkata", "ahmedabad", "jaipur", "chandigarh", "kochi", "coimbatore",
    "indore", "lucknow", "mysore", "mysuru", "thane", "navi mumbai",
    "telangana", "karnataka", "maharashtra", "haryana", "uttar pradesh",
    "tamil nadu", "kerala", "west bengal", "pan india", "remote - india",
    "remote (india)", "india (remote)",
)
ABROAD_MARKERS = (
    "united states", "u.s.a", "u.s.", "usa", "america",
    "california", "san francisco", "bay area", "new york", "seattle",
    "austin", "boston", "chicago", "denver", "atlanta", "texas",
    "washington", "los angeles", "san jose", "palo alto", "mountain view",
    "united kingdom", "england", "london", "manchester", "scotland",
    "canada", "toronto", "vancouver", "ontario", "montreal",
    "germany", "berlin", "munich", "netherlands", "amsterdam",
    "australia", "sydney", "melbourne", "singapore", "dubai", "uae",
    "ireland", "dublin", "poland", "warsaw", "remote - us", "remote, us",
    "remote (us)", "us remote",
)
US_STATE_RE = re.compile(
    r',\s*(AL|AK|AZ|AR|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|KS|KY|LA|MA|MD|ME|'
    r'MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|'
    r'UT|VA|VT|WA|WI|WV)\b',
    re.IGNORECASE,
)
FRONTEND_MARKERS = (
    "frontend", "front-end", "front end",
    "ui engineer", "ui developer", "ui/ux", "ux engineer",
    "react developer", "react.js developer", "reactjs developer",
    "angular developer", "vue developer", "vue.js",
)
FRONTEND_KEEP = (
    "full stack", "fullstack", "full-stack", "backend", "back-end", "back end",
)


def _experience_exceeds_cap(min_y: float, max_y: float, cap: float = MAX_JD_EXPERIENCE_YEARS) -> bool:
    return min_y > cap or max_y > cap


def _pair(min_y: float, max_y: float) -> Tuple[float, float]:
    if max_y < min_y:
        return max_y, min_y
    return min_y, max_y


def _ranges_from_text(text: str) -> list:
    if not text:
        return []
    found = []
    for match in RANGE_YEARS_RE.finditer(text):
        found.append(_pair(float(match.group(1)), float(match.group(2))))
    for match in PLUS_YEARS_RE.finditer(text):
        min_y = float(match.group(1))
        found.append((min_y, min_y + 3.0))
    for match in MIN_YEARS_RE.finditer(text):
        min_y = float(match.group(1))
        phrase = match.group(0).lower()
        if "more than" in phrase or phrase.startswith("over"):
            found.append((min_y + 0.1, min_y + 0.1))
        else:
            found.append((min_y, min_y))
    for match in EXP_PREFIX_RE.finditer(text):
        min_y = float(match.group(1))
        max_y = float(match.group(2)) if match.group(2) else min_y
        found.append(_pair(min_y, max_y))
    if not found:
        for match in SOLO_YEARS_RE.finditer(text):
            val = float(match.group(1))
            found.append((val, val))
    return found


def parse_experience_years(text: str) -> Optional[Tuple[float, float]]:
    ranges = _ranges_from_text(text or "")
    return ranges[0] if ranges else None


def _jd_experience_ranges(jd_text: str) -> list:
    found = []
    text = jd_text or ""
    for match in JD_EXP_RE.finditer(text):
        before = text[max(0, match.start() - 48):match.start()]
        if JD_HISTORY_BEFORE_RE.search(before):
            continue
        min_y = float(match.group(1))
        max_y = float(match.group(2)) if match.group(2) else min_y
        if "+" in match.group(0) and not match.group(2):
            max_y = min_y + 3.0
        if min_y > 15:
            continue
        found.append(_pair(min_y, max_y))
    return found


def is_job_experience_valid(
    job_data: dict,
    max_years: float = MAX_JD_EXPERIENCE_YEARS,
    require_jd: bool = True,
) -> Tuple[bool, str]:
    # Honour the caller's cap; MAX_JD_EXPERIENCE_YEARS is only the default.
    cap = float(max_years) if max_years else MAX_JD_EXPERIENCE_YEARS
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

    ranges = []
    for blob in (title, job_data.get("experience_required", "") or ""):
        ranges.extend(_ranges_from_text(blob))
    ranges.extend(_jd_experience_ranges(jd_text))

    for min_y, max_y in ranges:
        if _experience_exceeds_cap(min_y, max_y, cap=cap):
            return False, (
                f"Requires more than {cap:g} years of experience "
                f"(parsed {min_y:g}-{max_y:g})"
            )

    platform = (job_data.get("platform") or "").lower()
    if require_jd and platform == "linkedin" and len(jd_text) < MIN_JD_CHARS:
        return False, "LinkedIn JD missing; cannot verify experience"

    return True, "Passed experience boundaries check"


def is_career_listing_eligible(job_data: dict) -> Tuple[bool, str]:
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


def is_pure_frontend_role(title: str, jd_text: str = "") -> bool:
    t = (title or "").lower()
    if "react native" in t:
        return False
    if any(k in t for k in FRONTEND_KEEP):
        return False
    if any(m in t for m in FRONTEND_MARKERS):
        return True
    jd = (jd_text or "")[:400].lower()
    if jd and any(m in jd[:200] for m in ("this is a frontend", "this is a front-end", "front-end only")):
        return True
    return False


def _contains_marker(blob: str, marker: str) -> bool:
    return bool(re.search(rf'(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])', blob))


def is_location_allowed(job_data: dict) -> Tuple[bool, str]:
    location = (job_data.get("location") or "").strip()
    title = job_data.get("title") or ""
    jd = (job_data.get("jd_text") or "")[:1200]
    platform = (job_data.get("platform") or "").lower()
    blob = f"{location} {title} {jd}".lower()

    has_india = any(_contains_marker(blob, m) for m in INDIA_MARKERS)
    has_abroad = any(_contains_marker(blob, m) for m in ABROAD_MARKERS) or bool(US_STATE_RE.search(location))

    if has_abroad and not has_india:
        return False, f"Non-India location: '{location or title}'"
    if has_india:
        return True, "India location"
    if platform in INDIA_PLATFORMS:
        return True, "India job board"
    loc = location.lower()
    if not loc:
        return False, "Missing location"
    if "remote" in loc or "work from home" in loc or loc in {"wfh", "anywhere"}:
        return False, f"Remote outside India: '{location}'"
    return False, f"Non-India location: '{location}'"


def passes_hard_filters(
    job_data: dict,
    max_years: float = MAX_JD_EXPERIENCE_YEARS,
    require_jd: bool = True,
) -> Tuple[bool, str]:
    title = job_data.get("title") or ""
    jd = job_data.get("jd_text") or ""
    if is_pure_frontend_role(title, jd):
        return False, f"Frontend role: '{title}'"
    ok, reason = is_location_allowed(job_data)
    if not ok:
        return False, reason
    return is_job_experience_valid(job_data, max_years=max_years, require_jd=require_jd)

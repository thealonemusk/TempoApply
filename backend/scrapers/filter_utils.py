"""
Filter utilities — text parsing and strict experience/title boundary checks.
Enforces hard limits to ensure only entry-level / early-career (< 2 years exp) jobs are retained.
"""

import re
from typing import Optional, Tuple
from loguru import logger

# Keywords in job titles that indicate non-entry-level or senior positions
EXCLUDED_TITLE_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "staff", "principal", "manager",
    "director", "head", "architect", "sde 2", "sde-2", "sde2", "sde 3", "sde-3",
    "sde3", "sde ii", "sde-ii", "sde iii", "sde-iii", "level 2", "level 3", "l2", "l3", "expert",
    "vp", "vice president", "chief", "tech lead", "team lead", "experienced","QA","test"
    "consultant", "specialist", "5+", "3+", "4+", "6+", "7+", "8+"
]

# Patterns in job titles indicating level II/III or 2/3 (non-entry)
EXCLUDED_TITLE_REGEXES = [
    r'\b(?:ii|iii|iv|v)\b',         # Roman numerals II, III, IV, V as standalone words (e.g. "Software Engineer II")
    r'[-_\s](?:2|3|4|5)\b',         # Numbers 2, 3, 4 after space/dash (e.g. "Software Engineer - 2", "Developer 2")
]

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

    # Pattern 1: Range like "3-5 years", "0 to 2 yrs", "1 - 3 yrs"
    range_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr|y)?', clean_text)
    if range_match:
        min_y = float(range_match.group(1))
        max_y = float(range_match.group(2))
        return (min_y, max_y)

    # Pattern 2: "3+ years", "3 + years", "min 3 yrs", "minimum 3 years", "at least 3 years"
    plus_match = re.search(r'(?:minimum|min\.?|at least)?\s*(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?|yr|y)?', clean_text)
    if plus_match:
        min_y = float(plus_match.group(1))
        return (min_y, min_y + 3.0)

    # Pattern 3: Explicit requirement phrase e.g. "minimum 3 years", "at least 2 years"
    min_phrase_match = re.search(r'(?:minimum|min\.?|at least)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr|y)?', clean_text)
    if min_phrase_match:
        min_y = float(min_phrase_match.group(1))
        return (min_y, min_y + 2.0)

    # Pattern 4: Standalone years like "3 yrs", "2 years"
    standalone_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr|y)', clean_text)
    if standalone_match:
        val = float(standalone_match.group(1))
        return (val, val)

    return None


def is_job_experience_valid(job_data: dict, max_years: float = 2.0) -> Tuple[bool, str]:
    """
    Check if a job posting meets the hard boundary of requiring < 2 years of experience.

    Returns:
        (is_valid: bool, reason: str)
    """
    title = job_data.get("title", "").strip()
    title_lower = title.lower()

    # 1. Title Keyword & Regex Exclusion Check
    for keyword in EXCLUDED_TITLE_KEYWORDS:
        if keyword in title_lower:
            return False, f"Title contains senior/excluded keyword: '{keyword}' in '{title}'"

    for pattern in EXCLUDED_TITLE_REGEXES:
        if re.search(pattern, title_lower):
            return False, f"Title matches excluded level pattern: '{pattern}' in '{title}'"

    # 2. `experience_required` Field Check
    exp_str = job_data.get("experience_required", "").strip()
    if exp_str:
        exp_range = parse_experience_years(exp_str)
        if exp_range:
            min_y, max_y = exp_range
            # If minimum required experience exceeds max_years, or is >= 2.5 yrs
            if min_y >= 2.5 or min_y > max_years:
                return False, f"Experience field required ({exp_str}) exceeds threshold {max_years} years"
            # If range is e.g. 3-5 yrs (min=3 >= 2)
            if min_y >= 3.0:
                return False, f"Experience field required ({exp_str}) min years >= 3.0"

    # 3. Job Description Text Scan for explicit hard experience requirements
    jd_text = job_data.get("jd_text", "").strip()
    if jd_text:
        # Search for patterns like "3+ years of experience", "minimum 3 years", "4-6 years of experience"
        jd_exp_matches = re.finditer(
            r'(?:requir(?:e|ed|es)|must have|minimum|at least|\+|\b)\s*(\d+(?:\.\d+)?)\s*(?:\+|\-|to)?\s*(\d+(?:\.\d+)?)?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)?',
            jd_text.lower()
        )
        for match in jd_exp_matches:
            val1 = float(match.group(1)) if match.group(1) else 0.0
            val2 = float(match.group(2)) if match.group(2) else 0.0
            
            # Avoid matching false positives like "1-2 days" or small values like 0, 1, 2
            # Check if this phrase mentions 3+, 4+, 5+, 6+, 7+, 8+, 9+, 10+ years
            phrase = match.group(0)
            if any(term in phrase for term in ["3+", "4+", "5+", "6+", "7+", "8+", "9+", "10+"]):
                return False, f"JD contains high experience requirement: '{phrase}'"
                
            if val1 >= 3.0 or val2 >= 3.0:
                return False, f"JD explicitly requires {val1}-{val2} years of experience: '{phrase}'"

    return True, "Passed experience boundaries check"

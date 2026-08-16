"""Detect ATS type from a job URL."""
from urllib.parse import urlparse

ATS_HOST_MARKERS = (
    ("greenhouse.io", "greenhouse"),
    ("greenhouse.com", "greenhouse"),
    ("lever.co", "lever"),
    ("myworkdayjobs.com", "workday"),
    ("myworkday.com", "workday"),
    ("workday.com", "workday"),
    ("ashbyhq.com", "ashby"),
    ("icims.com", "custom"),
    ("smartrecruiters.com", "custom"),
    ("successfactors.com", "custom"),
    ("taleo.net", "custom"),
    ("jobvite.com", "custom"),
    ("bamboohr.com", "custom"),
    ("rippling.com", "custom"),
    ("dover.io", "custom"),
)


def detect_ats(url: str) -> str:
    if not url:
        return "unknown"
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    hay = f"{host}{path}"
    for marker, ats in ATS_HOST_MARKERS:
        if marker in hay:
            return ats
    return "unknown"


def apply_url_for_ats(url: str, ats: str) -> str:
    """Return the most likely apply-form URL for a known ATS."""
    if not url:
        return url
    cleaned = url.split("?")[0].rstrip("/")
    if ats == "lever" and not cleaned.endswith("/apply"):
        return cleaned + "/apply"
    if ats == "greenhouse" and "#" not in url:
        return url
    return url

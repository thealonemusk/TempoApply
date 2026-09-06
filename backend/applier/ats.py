"""Detect ATS type from a job URL."""
import re
from urllib.parse import unquote, urlparse

# Any absolute URL. We deliberately do NOT try to match ATS hosts inside this
# pattern: an inline marker cannot match a host at position 0 (jobs.lever.co/…)
# and, on a nested link, greedily swallows the outer URL. Candidates are
# extracted first and classified with detect_ats() instead.
URL_CANDIDATE_RE = re.compile(r"https?://[^\s\"'<>\\)\]}]+", re.I)

# Kept for backwards compatibility with any caller that imported it.
ATS_URL_RE = URL_CANDIDATE_RE

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


TRAILING_JUNK = ").,]}>'\"&;"


def _nested_candidates(url: str):
    """
    Yield the URL itself plus any absolute URL embedded in it.

    LinkedIn wraps the real target in a query string
    (…/jobs/view/x?externalApply=https://boards.greenhouse.io/…), so the
    embedded link — not the wrapper — is the one worth applying on. Inner
    candidates are yielded first, longest offset last, so the innermost
    (most specific) target wins.
    """
    offsets = [m.start() for m in re.finditer(r"https?://", url, re.I)]
    for start in reversed(offsets):
        yield url[start:].rstrip(TRAILING_JUNK)


def first_ats_url(*texts: str) -> str:
    """Find the first Greenhouse/Lever/Workday/etc URL in HTML, JD, or href lists."""
    for text in texts:
        if not text:
            continue
        raw = str(text).replace("&amp;", "&")
        # LinkedIn double-encodes some redirect targets.
        decoded = unquote(raw)
        if "%3A%2F%2F" in decoded or "%2F" in decoded:
            decoded = unquote(decoded)
        for candidate in URL_CANDIDATE_RE.findall(decoded):
            for url in _nested_candidates(candidate):
                if detect_ats(url) != "unknown":
                    return url
    return ""


# ── Appliability ─────────────────────────────────────────────────────────────
# Auto-apply only works where we can reach a real form: a supported ATS, or
# LinkedIn Easy Apply. Everything else (staffing portals, bespoke career
# pages behind auth) has to be done by hand, and the queue should say so
# rather than spending a full timeout discovering it.

SUPPORTED_ATS = ("greenhouse", "lever", "workday", "ashby")

APPLY_METHOD_AUTO = SUPPORTED_ATS + ("linkedin_easy",)


def apply_method(
    url: str,
    apply_url: str = "",
    ats_type: str = "",
    easy_apply: bool = False,
    platform: str = "",
) -> str:
    """
    Classify how a posting can be applied to.

    Returns one of the SUPPORTED_ATS values, "linkedin_easy", or "manual".
    Prefers a scan-resolved apply_url, since that is the company form itself.
    """
    for candidate in (apply_url, url):
        ats = detect_ats(candidate) if candidate else "unknown"
        if ats in SUPPORTED_ATS:
            return ats
    if (ats_type or "").lower() in SUPPORTED_ATS:
        return ats_type.lower()
    if easy_apply and "linkedin" in (platform or "").lower():
        return "linkedin_easy"
    return "manual"


def is_auto_appliable(method: str) -> bool:
    return method in APPLY_METHOD_AUTO

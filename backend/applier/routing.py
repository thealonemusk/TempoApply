"""
Decide, per job, whether a bot can apply or a human must.

This exists because the apply pipeline used to assume every job was a LinkedIn
job. It called `ensure_linkedin_session()` once, unconditionally, before
touching any job — so applying to a Greenhouse posting sat waiting for a
LinkedIn login that was never coming, and the whole run died with a closed
browser. One channel's login gate must never block another's.

Three outcomes:

  AUTO    a public ATS form with no account: Greenhouse, Lever, Ashby. The bot
          fills and (optionally) submits it.
  LOGIN   an ATS behind a per-company account: Workday tenants, amazon.jobs,
          Microsoft, Google. Automatable only where credentials are stored.
  MANUAL  everything else, and LinkedIn specifically. Routed to the human queue
          and applied through the browser extension.

LinkedIn is MANUAL by policy, not by capability. Automated Easy Apply at volume
is the reliable way to get the account restricted, and the account is worth more
than the applications.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from backend.applier.ats import detect_ats, first_ats_url

# ATS platforms whose application form is public.
NO_ACCOUNT_ATS = frozenset({"greenhouse", "lever", "ashby"})

# ATS platforms that put the form behind a sign-in.
ACCOUNT_ATS = frozenset({"workday"})

# Hosts that always require the candidate's own account.
ACCOUNT_HOSTS = (
    "amazon.jobs",
    "careers.microsoft.com",
    "careers.google.com",
    "google.com/about/careers",
)

MANUAL_HOSTS = ("linkedin.com", "naukri.com", "indeed.com", "instahyre.com", "glassdoor.")


class Route(str, Enum):
    AUTO = "auto"
    LOGIN = "login"
    MANUAL = "manual"


@dataclass(frozen=True)
class Routing:
    """Where a job goes, and the URL to actually open."""

    route: Route
    apply_url: str
    ats: str
    reason: str

    @property
    def is_auto(self) -> bool:
        return self.route is Route.AUTO


def _host(url: str) -> str:
    try:
        return (urlparse(url or "").netloc or "").lower()
    except ValueError:
        return ""


def classify(url: str, jd_text: str = "", company: str = "") -> Routing:
    """
    Work out how a posting can be applied to.

    A LinkedIn listing often names the employer's real ATS link inside the
    description; following that turns an un-automatable listing into an
    automatable one, which is the single biggest win available — only 5% of a
    LinkedIn-sourced pool is reachable without it.
    """
    url = (url or "").strip()
    host = _host(url)
    direct_ats = detect_ats(url)

    # 1. Already pointing at a public ATS form.
    if direct_ats in NO_ACCOUNT_ATS:
        return Routing(Route.AUTO, url, direct_ats, f"direct {direct_ats} form")

    # 2. Already pointing at an ATS that needs an account.
    if direct_ats in ACCOUNT_ATS:
        return Routing(Route.LOGIN, url, direct_ats,
                       f"{direct_ats} requires an account for this employer")
    if any(marker in host for marker in ACCOUNT_HOSTS):
        return Routing(Route.LOGIN, url, direct_ats or "custom",
                       f"{host} requires a candidate account")

    # 3. A job board listing that names the real ATS link in its description.
    resolved = first_ats_url(jd_text, url)
    if resolved:
        resolved_ats = detect_ats(resolved)
        if resolved_ats in NO_ACCOUNT_ATS:
            return Routing(Route.AUTO, resolved, resolved_ats,
                           f"resolved to a {resolved_ats} form in the description")
        if resolved_ats in ACCOUNT_ATS:
            return Routing(Route.LOGIN, resolved, resolved_ats,
                           f"resolved to {resolved_ats}, which needs an account")

    # 4. LinkedIn and the other boards: a human applies, through the extension.
    if any(marker in host for marker in MANUAL_HOSTS):
        board = next((m.strip(".") for m in MANUAL_HOSTS if m in host), host)
        return Routing(Route.MANUAL, url, direct_ats,
                       f"{board} listing with no external form — apply by hand")

    return Routing(Route.MANUAL, url, direct_ats,
                   "no recognised application form — apply by hand")


def route_job(job) -> Routing:
    """Classify a `Job` row."""
    return classify(
        url=getattr(job, "url", "") or "",
        jd_text=getattr(job, "jd_text", "") or "",
        company=getattr(job, "company", "") or "",
    )


def needs_linkedin(routings) -> bool:
    """
    Whether this batch needs a LinkedIn session at all.

    Nothing auto-appliable ever does, so the sign-in prompt should not appear
    for a run made entirely of Greenhouse forms.
    """
    return any("linkedin" in _host(r.apply_url) for r in routings if r.is_auto)

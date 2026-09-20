"""Shared job posting freshness window (default: 72 hours)."""

JOB_FRESHNESS_HOURS = 72
JOB_FRESHNESS_SECONDS = JOB_FRESHNESS_HOURS * 3600
JOB_FRESHNESS_DAYS = JOB_FRESHNESS_HOURS / 24

# LinkedIn f_TPR=r{seconds}
LINKEDIN_TIME_FILTER = f"r{JOB_FRESHNESS_SECONDS}"

# Naukri / Indeed age filters use whole days. Career boards stay open longer
# than LinkedIn's 72h guest window, so keep a week of Naukri results.
NAUKRI_JOB_AGE_DAYS = 7
INDEED_FROMAGE_DAYS = max(1, round(JOB_FRESHNESS_HOURS / 24))

# Greenhouse / Lever / Workday posting age (hours). Missing dates are treated
# as fresh; only dated-stale postings are dropped.
#
# Deliberately much wider than LinkedIn's window. A company board keeps a
# requisition open for weeks, so a 64-hour cut discarded almost everything —
# it is why direct boards contributed 10 jobs out of 177 while holding over a
# thousand reachable roles. Re-applying is not a risk here: the seen ledger
# blocks anything already acted on.
CAREER_FRESHNESS_HOURS = 14 * 24

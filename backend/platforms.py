"""Platform constants — single source of truth for scan targets."""

# Default scan: LinkedIn + Naukri + direct company career sites
SCAN_PLATFORMS = [
    "linkedin",
    "naukri",
    "company_careers",
]

DEFAULT_SCAN_PLATFORMS = SCAN_PLATFORMS

# Scrapers kept in the codebase but not run unless explicitly requested.
OPTIONAL_PLATFORMS = ["indeed", "instahyre", "wellfound"]

# Deduplicated, order-preserving union of everything a Job.platform may hold.
ALL_PLATFORMS = list(
    dict.fromkeys(SCAN_PLATFORMS + OPTIONAL_PLATFORMS + ["manual"])
)

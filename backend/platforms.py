"""Platform constants — single source of truth for scan targets."""

# Default scan: LinkedIn + Naukri + direct company career sites
SCAN_PLATFORMS = [
    "linkedin",
    "naukri",
    "company_careers",
]

DEFAULT_SCAN_PLATFORMS = SCAN_PLATFORMS

# Scrapers kept in codebase but not run unless explicitly requested
OPTIONAL_PLATFORMS = ["indeed", "naukri", "instahyre", "wellfound"]

ALL_PLATFORMS = SCAN_PLATFORMS + OPTIONAL_PLATFORMS + ["manual"]

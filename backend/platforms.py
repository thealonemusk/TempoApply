"""Platform constants — single source of truth for scan targets."""

# Default scan: LinkedIn + Naukri + direct company career sites
# Order matters: company boards first. They are the only source that yields a
# directly applicable URL — a measured 14 Greenhouse boards hold 1,363 India
# engineering roles, where a LinkedIn-sourced pool of 177 contained 9 reachable
# ones. LinkedIn stays for coverage, but its listings route to manual apply.
SCAN_PLATFORMS = [
    "company_careers",
    "bigtech",
    "linkedin",
    "naukri",
]

DEFAULT_SCAN_PLATFORMS = SCAN_PLATFORMS

# Scrapers kept in codebase but not run unless explicitly requested
OPTIONAL_PLATFORMS = ["indeed", "naukri", "instahyre", "wellfound"]

ALL_PLATFORMS = SCAN_PLATFORMS + OPTIONAL_PLATFORMS + ["manual"]

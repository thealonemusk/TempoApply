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

# Sources that create jobs without a scraper: added by hand, or tracked by the
# browser extension. "extension" was missing, so every application recorded
# from the extension was absent from the analytics platform breakdown — the
# rows existed, nothing counted them.
MANUAL_SOURCES = ["manual", "extension"]


def _unique(*groups) -> list:
    """Preserve order, drop repeats — "naukri" is in two of these lists."""
    seen, out = set(), []
    for group in groups:
        for name in group:
            if name not in seen:
                seen.add(name)
                out.append(name)
    return out


ALL_PLATFORMS = _unique(SCAN_PLATFORMS, OPTIONAL_PLATFORMS, MANUAL_SOURCES)

"""
Top Indian Software / Tech Companies — career site metadata.

ATS types:
  - "greenhouse"  → uses boards-api.greenhouse.io; provide `api_id` = board slug
  - "lever"       → uses api.lever.co;              provide `api_id` = company slug
  - "custom"      → direct HTML scrape;              provide `careers_url`
  - "skip"        → known to be too JS-heavy or blocks scrapers; ignored in v1

Priority order: greenhouse/lever companies are most reliable (JSON APIs, no auth).
Board IDs verified against live APIs (404 / wrong-company entries removed).
"""

# Shared India location keywords used across companies
INDIA_LOCS = [
    "india", "bangalore", "bengaluru", "hyderabad", "pune", "mumbai",
    "delhi", "noida", "gurgaon", "gurugram", "chennai", "remote - india",
]

TOP_COMPANIES = [
    # ──────────────────── Greenhouse ATS (verified) ─────────────────────
    {
        "name": "Groww",
        "type": "greenhouse",
        "api_id": "groww",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Postman",
        "type": "greenhouse",
        "api_id": "postman",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "InMobi",
        "type": "greenhouse",
        "api_id": "inmobi",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "PhonePe",
        "type": "greenhouse",
        "api_id": "phonepe",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "HackerRank",
        "type": "greenhouse",
        "api_id": "hackerrank",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "ThoughtWorks",
        "type": "greenhouse",
        "api_id": "thoughtworks",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Druva",
        "type": "greenhouse",
        "api_id": "druva",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Tower Research Capital",
        "type": "greenhouse",
        "api_id": "towerresearchcapital",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Mixpanel",
        "type": "greenhouse",
        "api_id": "mixpanel",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Samsara",
        "type": "greenhouse",
        "api_id": "samsara",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Figma",
        "type": "greenhouse",
        "api_id": "figma",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Datadog",
        "type": "greenhouse",
        "api_id": "datadog",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Stripe",
        "type": "greenhouse",
        "api_id": "stripe",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Databricks",
        "type": "greenhouse",
        "api_id": "databricks",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Cloudflare",
        "type": "greenhouse",
        "api_id": "cloudflare",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Twilio",
        "type": "greenhouse",
        "api_id": "twilio",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Okta",
        "type": "greenhouse",
        "api_id": "okta",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "MongoDB",
        "type": "greenhouse",
        "api_id": "mongodb",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Elastic",
        "type": "greenhouse",
        "api_id": "elastic",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Airbnb",
        "type": "greenhouse",
        "api_id": "airbnb",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Dropbox",
        "type": "greenhouse",
        "api_id": "dropbox",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Asana",
        "type": "greenhouse",
        "api_id": "asana",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Coinbase",
        "type": "greenhouse",
        "api_id": "coinbase",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "GitLab",
        "type": "greenhouse",
        "api_id": "gitlab",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Pinterest",
        "type": "greenhouse",
        "api_id": "pinterest",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Reddit",
        "type": "greenhouse",
        "api_id": "reddit",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Discord",
        "type": "greenhouse",
        "api_id": "discord",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Brex",
        "type": "greenhouse",
        "api_id": "brex",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Affirm",
        "type": "greenhouse",
        "api_id": "affirm",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Robinhood",
        "type": "greenhouse",
        "api_id": "robinhood",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Block",
        "type": "greenhouse",
        "api_id": "block",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Instacart",
        "type": "greenhouse",
        "api_id": "instacart",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Lyft",
        "type": "greenhouse",
        "api_id": "lyft",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Anthropic",
        "type": "greenhouse",
        "api_id": "anthropic",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Pure Storage",
        "type": "greenhouse",
        "api_id": "purestorage",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Rubrik",
        "type": "greenhouse",
        "api_id": "rubrik",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Toast",
        "type": "greenhouse",
        "api_id": "toast",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Roblox",
        "type": "greenhouse",
        "api_id": "roblox",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Quince",
        "type": "greenhouse",
        "api_id": "quince",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Crunchyroll",
        "type": "greenhouse",
        "api_id": "crunchyroll",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Khan Academy",
        "type": "greenhouse",
        "api_id": "khanacademy",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Commvault",
        "type": "greenhouse",
        "api_id": "commvault",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Adyen",
        "type": "greenhouse",
        "api_id": "adyen",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Sumo Logic",
        "type": "greenhouse",
        "api_id": "sumologic",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Turing",
        "type": "greenhouse",
        "api_id": "turing",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "LinkedIn",
        "type": "greenhouse",
        "api_id": "linkedin",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Amplitude",
        "type": "greenhouse",
        "api_id": "amplitude",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "LaunchDarkly",
        "type": "greenhouse",
        "api_id": "launchdarkly",
        "location_filter": INDIA_LOCS,
    },

    # ──────────────────── Lever ATS (verified) ─────────────────────
    {
        "name": "Spotify",
        "type": "lever",
        "api_id": "spotify",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Palantir",
        "type": "lever",
        "api_id": "palantir",
        "location_filter": INDIA_LOCS,
    },

    # ──────────────────── Custom / HTML Scrape ─────────────────────
    {
        "name": "Flipkart",
        "type": "custom",
        "careers_url": "https://www.flipkartcareers.com/#!/joblist",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Paytm",
        "type": "custom",
        "careers_url": "https://paytm.com/careers#jobs",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Zomato",
        "type": "custom",
        "careers_url": "https://www.zomato.com/careers",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Dream11",
        "type": "custom",
        "careers_url": "https://www.dream11.com/careers#available-positions",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "MakeMyTrip",
        "type": "custom",
        "careers_url": "https://careers.makemytrip.com/",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "OYO Rooms",
        "type": "custom",
        "careers_url": "https://www.oyorooms.com/careers/",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Byju's",
        "type": "custom",
        "careers_url": "https://byjus.com/careers/",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Infosys",
        "type": "custom",
        "careers_url": "https://career.infosys.com/joblist",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "Wipro",
        "type": "custom",
        "careers_url": "https://careers.wipro.com/careers-home/jobs?page=1&location=India",
        "location_filter": INDIA_LOCS,
    },
    {
        "name": "HCL Technologies",
        "type": "custom",
        "careers_url": "https://www.hcltech.com/careers/jobs?location=India",
        "location_filter": INDIA_LOCS,
    },

    # ──────────────────── Skip (JS-heavy / anti-scrape) ─────────────────────
    {"name": "TCS", "type": "skip", "reason": "iXP portal requires login"},
    {"name": "Accenture India", "type": "skip", "reason": "Workday — JS-heavy"},
    {"name": "Amazon India", "type": "skip", "reason": "use LinkedIn/Naukri instead"},
    {"name": "Microsoft India", "type": "skip", "reason": "use LinkedIn/Naukri instead"},
    {"name": "IBM India", "type": "skip", "reason": "Kenexa portal — too complex"},
    {"name": "SAP India", "type": "skip", "reason": "SAP SuccessFactors — too complex"},
    {"name": "Oracle India", "type": "skip", "reason": "Oracle HCM — login required"},
    {"name": "Adobe India", "type": "skip", "reason": "Workday — JS-heavy"},
    {"name": "Swiggy", "type": "skip", "reason": "Greenhouse board slug retired"},
    {"name": "Razorpay", "type": "skip", "reason": "Greenhouse board slug retired"},
    {"name": "CRED", "type": "skip", "reason": "Greenhouse board slug retired"},
    {"name": "Meesho", "type": "skip", "reason": "Greenhouse board slug retired"},
]

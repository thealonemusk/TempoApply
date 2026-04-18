"""
Top 100 Indian Software / Tech Companies — career site metadata.

ATS types:
  - "greenhouse"  → uses boards-api.greenhouse.io; provide `api_id` = board slug
  - "lever"       → uses api.lever.co;              provide `api_id` = company slug
  - "workable"    → uses apply.workable.com;         provide `api_id` = subdomain slug (limited parsing)
  - "custom"      → direct HTML scrape;              provide `careers_url`
  - "skip"        → known to be too JS-heavy or blocks scrapers; ignored in v1

Priority order: greenhouse/lever companies are most reliable (JSON APIs, no auth).
"""

TOP_COMPANIES = [
    # ──────────────────── Greenhouse ATS ─────────────────────
    {
        "name": "Google India",
        "type": "greenhouse",
        "api_id": "google",
        "location_filter": ["bangalore", "hyderabad", "india"],
    },
    {
        "name": "Swiggy",
        "type": "greenhouse",
        "api_id": "swiggy",
        "location_filter": ["bangalore", "india"],
    },
    {
        "name": "Razorpay",
        "type": "greenhouse",
        "api_id": "razorpay",
        "location_filter": ["bangalore", "india"],
    },
    {
        "name": "CRED",
        "type": "greenhouse",
        "api_id": "cred",
        "location_filter": ["bangalore", "india"],
    },
    {
        "name": "Meesho",
        "type": "greenhouse",
        "api_id": "meesho",
        "location_filter": ["bangalore", "india"],
    },
    {
        "name": "Groww",
        "type": "greenhouse",
        "api_id": "groww",
        "location_filter": ["bangalore", "india"],
    },
    {
        "name": "Postman",
        "type": "greenhouse",
        "api_id": "postman",
        "location_filter": ["bangalore", "india"],
    },
    {
        "name": "Urban Company",
        "type": "greenhouse",
        "api_id": "urbancompany",
        "location_filter": ["india"],
    },
    {
        "name": "BrowserStack",
        "type": "greenhouse",
        "api_id": "browserstack",
        "location_filter": ["india"],
    },
    {
        "name": "Chargebee",
        "type": "greenhouse",
        "api_id": "chargebee",
        "location_filter": ["india"],
    },
    {
        "name": "Clevertap",
        "type": "greenhouse",
        "api_id": "clevertap",
        "location_filter": ["india"],
    },
    {
        "name": "Mixpanel",
        "type": "greenhouse",
        "api_id": "mixpanel",
        "location_filter": ["india"],
    },
    {
        "name": "Samsara",
        "type": "greenhouse",
        "api_id": "samsara",
        "location_filter": ["india"],
    },
    {
        "name": "Hasura",
        "type": "greenhouse",
        "api_id": "hasura",
        "location_filter": ["india"],
    },
    {
        "name": "Jupiter (Fi Money)",
        "type": "greenhouse",
        "api_id": "jupitermoney",
        "location_filter": ["india"],
    },
    {
        "name": "Gojek (GoTo India)",
        "type": "greenhouse",
        "api_id": "gojek",
        "location_filter": ["india", "bangalore"],
    },
    {
        "name": "InMobi",
        "type": "greenhouse",
        "api_id": "inmobi",
        "location_filter": ["india"],
    },
    {
        "name": "Confluent",
        "type": "greenhouse",
        "api_id": "confluent",
        "location_filter": ["india", "bangalore", "pune"],
    },
    {
        "name": "Datadog",
        "type": "greenhouse",
        "api_id": "datadog",
        "location_filter": ["india"],
    },
    {
        "name": "HashiCorp",
        "type": "greenhouse",
        "api_id": "hashicorp",
        "location_filter": ["india"],
    },
    {
        "name": "Figma",
        "type": "greenhouse",
        "api_id": "figma",
        "location_filter": ["india"],
    },
    {
        "name": "Lenskart",
        "type": "greenhouse",
        "api_id": "lenskart",
        "location_filter": ["india"],
    },
    {
        "name": "Khatabook",
        "type": "greenhouse",
        "api_id": "khatabook",
        "location_filter": ["india"],
    },
    {
        "name": "Leadsquared",
        "type": "greenhouse",
        "api_id": "leadsquared",
        "location_filter": ["india"],
    },
    {
        "name": "Nimble Wireless",
        "type": "greenhouse",
        "api_id": "nimble",
        "location_filter": ["india"],
    },

    # ──────────────────── Lever ATS ─────────────────────
    {
        "name": "PhonePe",
        "type": "lever",
        "api_id": "phonepe",
        "location_filter": ["bangalore", "india"],
    },
    {
        "name": "Zepto",
        "type": "lever",
        "api_id": "zeptonow",
        "location_filter": ["india"],
    },
    {
        "name": "Dunzo",
        "type": "lever",
        "api_id": "dunzo",
        "location_filter": ["india"],
    },
    {
        "name": "Darwinbox",
        "type": "lever",
        "api_id": "darwinbox",
        "location_filter": ["india"],
    },
    {
        "name": "Sprinklr",
        "type": "lever",
        "api_id": "sprinklr",
        "location_filter": ["india", "gurgaon"],
    },
    {
        "name": "Nykaa",
        "type": "lever",
        "api_id": "nykaa",
        "location_filter": ["india"],
    },
    {
        "name": "Ola",
        "type": "lever",
        "api_id": "ola-cabs",
        "location_filter": ["india"],
    },
    {
        "name": "ShareChat",
        "type": "lever",
        "api_id": "sharechat",
        "location_filter": ["india"],
    },
    {
        "name": "Juspay",
        "type": "lever",
        "api_id": "juspay",
        "location_filter": ["india"],
    },
    {
        "name": "Browserless",
        "type": "lever",
        "api_id": "browserless",
        "location_filter": ["india"],
    },
    {
        "name": "Open Financial Technologies",
        "type": "lever",
        "api_id": "openfinancial",
        "location_filter": ["india"],
    },
    {
        "name": "Vedantu",
        "type": "lever",
        "api_id": "vedantu",
        "location_filter": ["india"],
    },
    {
        "name": "Unacademy",
        "type": "lever",
        "api_id": "unacademy",
        "location_filter": ["india"],
    },
    {
        "name": "Freshworks",
        "type": "lever",
        "api_id": "freshworks",
        "location_filter": ["india", "chennai"],
    },
    {
        "name": "Porter",
        "type": "lever",
        "api_id": "porter",
        "location_filter": ["india"],
    },
    {
        "name": "Pocketfm",
        "type": "lever",
        "api_id": "pocketfm",
        "location_filter": ["india"],
    },
    {
        "name": "Slice",
        "type": "lever",
        "api_id": "sliceit",
        "location_filter": ["india"],
    },
    {
        "name": "Rupeek",
        "type": "lever",
        "api_id": "rupeek",
        "location_filter": ["india"],
    },
    {
        "name": "Cars24",
        "type": "lever",
        "api_id": "cars24",
        "location_filter": ["india"],
    },
    {
        "name": "Simpl",
        "type": "lever",
        "api_id": "simpl",
        "location_filter": ["india"],
    },
    {
        "name": "OneCard",
        "type": "lever",
        "api_id": "onecard",
        "location_filter": ["india"],
    },
    {
        "name": "Niyo Solutions",
        "type": "lever",
        "api_id": "niyo",
        "location_filter": ["india"],
    },
    {
        "name": "Creditvidya",
        "type": "lever",
        "api_id": "creditvidya",
        "location_filter": ["india"],
    },
    {
        "name": "Yellow.ai",
        "type": "lever",
        "api_id": "yellowai",
        "location_filter": ["india"],
    },

    # ──────────────────── Custom / HTML Scrape ─────────────────────
    {
        "name": "Flipkart",
        "type": "custom",
        "careers_url": "https://www.flipkartcareers.com/#!/joblist",
        "location_filter": ["bangalore", "india"],
    },
    {
        "name": "Paytm",
        "type": "custom",
        "careers_url": "https://paytm.com/careers#jobs",
        "location_filter": ["india"],
    },
    {
        "name": "Zomato",
        "type": "custom",
        "careers_url": "https://www.zomato.com/careers",
        "location_filter": ["india"],
    },
    {
        "name": "Dream11",
        "type": "custom",
        "careers_url": "https://www.dream11.com/careers#available-positions",
        "location_filter": ["india"],
    },
    {
        "name": "MakeMyTrip",
        "type": "custom",
        "careers_url": "https://careers.makemytrip.com/",
        "location_filter": ["india"],
    },
    {
        "name": "OYO Rooms",
        "type": "custom",
        "careers_url": "https://www.oyorooms.com/careers/",
        "location_filter": ["india"],
    },
    {
        "name": "Byju's",
        "type": "custom",
        "careers_url": "https://byjus.com/careers/",
        "location_filter": ["india"],
    },
    {
        "name": "Paytm Money",
        "type": "custom",
        "careers_url": "https://jobs.lever.co/paytmmoney",
        "location_filter": ["india"],
    },
    {
        "name": "Infosys",
        "type": "custom",
        "careers_url": "https://career.infosys.com/joblist",
        "location_filter": ["india"],
    },
    {
        "name": "Wipro",
        "type": "custom",
        "careers_url": "https://careers.wipro.com/careers-home/jobs?page=1&location=India",
        "location_filter": ["india"],
    },
    {
        "name": "HCL Technologies",
        "type": "custom",
        "careers_url": "https://www.hcltech.com/careers/jobs?location=India",
        "location_filter": ["india"],
    },
    {
        "name": "Tech Mahindra",
        "type": "custom",
        "careers_url": "https://careers.techmahindra.com/en/jobs/",
        "location_filter": ["india"],
    },
    {
        "name": "Cognizant",
        "type": "custom",
        "careers_url": "https://careers.cognizant.com/in/en/search-results",
        "location_filter": ["india"],
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
]

"""
Check every company board in TOP_COMPANIES, and probe candidates for new ones.

Sourcing now leads with Greenhouse and Lever boards, because those are the only
channel that yields a directly applicable URL with no account: a measured 14
boards returned 175 India engineering roles, where the entire LinkedIn-sourced
database of 177 jobs contained just 9 reachable ones.

A board id that has gone stale is silent — the scraper logs a warning nobody
reads and that company simply stops appearing. This makes that visible.

    python scripts/verify_boards.py              # check the configured list
    python scripts/verify_boards.py --candidates # also probe proposed new boards
    python scripts/verify_boards.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from backend.scrapers.company_list import TOP_COMPANIES  # noqa: E402

TIMEOUT = 15
INDIA = ("india", "bangalore", "bengaluru", "hyderabad", "pune", "mumbai",
         "delhi", "noida", "gurgaon", "gurugram", "chennai", "remote")
ENGINEERING = ("engineer", "developer", "sde", "software", "backend",
               "full stack", "fullstack", "platform", "infrastructure")

# Boards worth adding for a FAANG / Fortune-100 target list. Guesses are cheap;
# this script is what turns them into verified entries.
CANDIDATES: List[Dict[str, str]] = [
    {"name": "Databricks", "type": "greenhouse", "api_id": "databricks"},
    {"name": "Snowflake", "type": "greenhouse", "api_id": "snowflake"},
    {"name": "Confluent", "type": "greenhouse", "api_id": "confluent"},
    {"name": "MongoDB", "type": "greenhouse", "api_id": "mongodb"},
    {"name": "Elastic", "type": "greenhouse", "api_id": "elastic"},
    {"name": "HashiCorp", "type": "greenhouse", "api_id": "hashicorp"},
    {"name": "Cloudflare", "type": "greenhouse", "api_id": "cloudflare"},
    {"name": "Twilio", "type": "greenhouse", "api_id": "twilio"},
    {"name": "Airbnb", "type": "greenhouse", "api_id": "airbnb"},
    {"name": "Coinbase", "type": "greenhouse", "api_id": "coinbase"},
    {"name": "Robinhood", "type": "greenhouse", "api_id": "robinhood"},
    {"name": "Reddit", "type": "greenhouse", "api_id": "reddit"},
    {"name": "Discord", "type": "greenhouse", "api_id": "discord"},
    {"name": "Canva", "type": "lever", "api_id": "canva"},
    {"name": "Atlassian", "type": "lever", "api_id": "atlassian"},
    {"name": "Netflix", "type": "lever", "api_id": "netflix"},
    {"name": "Plaid", "type": "lever", "api_id": "plaid"},
    {"name": "Rippling", "type": "greenhouse", "api_id": "rippling"},
    {"name": "Notion", "type": "greenhouse", "api_id": "notion"},
    {"name": "Grammarly", "type": "greenhouse", "api_id": "grammarly"},
    {"name": "Zscaler", "type": "greenhouse", "api_id": "zscaler"},
    {"name": "Nutanix", "type": "greenhouse", "api_id": "nutanix"},
    {"name": "Arista Networks", "type": "greenhouse", "api_id": "aristanetworks"},
    {"name": "Palo Alto Networks", "type": "greenhouse", "api_id": "paloaltonetworks"},
    {"name": "Zomato", "type": "greenhouse", "api_id": "zomato"},
    {"name": "Swiggy", "type": "greenhouse", "api_id": "swiggy"},
    {"name": "Razorpay", "type": "greenhouse", "api_id": "razorpay"},
    {"name": "Meesho", "type": "greenhouse", "api_id": "meesho"},
    {"name": "Zepto", "type": "greenhouse", "api_id": "zeptonow"},
    {"name": "CRED", "type": "greenhouse", "api_id": "cred"},
    {"name": "Flipkart", "type": "greenhouse", "api_id": "flipkart"},
    {"name": "Uber", "type": "greenhouse", "api_id": "uber"},
]


def probe(company: Dict[str, str]) -> Dict[str, object]:
    kind, api_id, name = company.get("type"), company.get("api_id", ""), company.get("name", "?")
    out: Dict[str, object] = {"name": name, "type": kind, "api_id": api_id,
                              "ok": False, "total": 0, "india": 0, "engineering": 0, "note": ""}
    if kind == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{api_id}/jobs"
    elif kind == "lever":
        url = f"https://api.lever.co/v0/postings/{api_id}?mode=json"
    else:
        out["note"] = f"skipped ({kind})"
        return out

    try:
        resp = requests.get(url, timeout=TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        out["note"] = f"error: {str(exc)[:50]}"
        return out

    if resp.status_code != 200:
        out["note"] = f"HTTP {resp.status_code}"
        return out

    try:
        payload = resp.json()
    except Exception:
        out["note"] = "non-JSON response"
        return out

    jobs = payload.get("jobs", []) if kind == "greenhouse" else payload
    if not isinstance(jobs, list):
        out["note"] = "unexpected payload"
        return out

    def location_of(job: dict) -> str:
        if kind == "greenhouse":
            return (job.get("location") or {}).get("name", "") or ""
        cats = job.get("categories") or {}
        return cats.get("location", "") or ""

    india = [j for j in jobs if any(m in location_of(j).lower() for m in INDIA)]
    eng = [j for j in india if any(k in (j.get("title", "") or "").lower() for k in ENGINEERING)]

    out.update(ok=True, total=len(jobs), india=len(india), engineering=len(eng))
    return out


def run(companies: List[Dict[str, str]], label: str) -> List[Dict[str, object]]:
    boards = [c for c in companies if c.get("type") in ("greenhouse", "lever")]
    print(f"\n{label}: probing {len(boards)} boards\n")
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(probe, boards))

    live = [r for r in results if r["ok"]]
    dead = [r for r in results if not r["ok"]]
    live.sort(key=lambda r: -r["engineering"])

    print(f"  {'company':28} {'type':11} {'posted':>7} {'india':>6} {'eng':>5}")
    for r in live:
        if r["engineering"]:
            print(f"  {r['name'][:28]:28} {r['type']:11} {r['total']:7} {r['india']:6} {r['engineering']:5}")
    quiet = [r for r in live if not r["engineering"]]
    if quiet:
        print(f"\n  live but no India engineering roles right now: "
              f"{', '.join(r['name'] for r in quiet)}")
    if dead:
        print(f"\n  BROKEN ({len(dead)}) — these silently contribute nothing:")
        for r in dead:
            print(f"    {r['name'][:28]:28} {r['api_id'][:22]:24} {r['note']}")

    print(f"\n  reachable India engineering roles: {sum(r['engineering'] for r in live)}")
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", action="store_true", help="also probe proposed new boards")
    ap.add_argument("--json", metavar="PATH", help="write full results as JSON")
    args = ap.parse_args()

    results = run(TOP_COMPANIES, "CONFIGURED (TOP_COMPANIES)")
    if args.candidates:
        results += run(CANDIDATES, "CANDIDATES for a FAANG / Fortune-100 list")
        good = [r for r in results if r["ok"] and r["engineering"]]
        print(f"\n  => {len(good)} boards currently worth scraping")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\n  wrote {args.json}")


if __name__ == "__main__":
    main()

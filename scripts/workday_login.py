"""
Manage the per-tenant Workday logins.

Workday gives every employer its own isolated tenant and its own account
database, so there is no single "Workday login" — an account at Intel is
meaningless at Cisco. Create each account once by hand on the employer's site,
record it here, and the apply run signs in on its own from then on.

    python scripts/workday_login.py list          # what is recorded, what is missing
    python scripts/workday_login.py add intel     # prompts, password is not echoed
    python scripts/workday_login.py remove intel
    python scripts/workday_login.py check <url>   # what would be used for this job

The password is read with getpass, never taken as an argument — a password on
the command line ends up in shell history and in the process list.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.applier.workday_creds import (  # noqa: E402
    credentials_for, delete_account, load_accounts, missing_tenants,
    save_account, signup_url, store_path, tenant_of,
)
from backend.db.models import Job, SessionLocal  # noqa: E402


def _workday_jobs():
    db = SessionLocal()
    try:
        return [
            (j.company, j.url) for j in db.query(Job)
            .filter(Job.url.like("%myworkday%"))
            .filter(~Job.status.in_(["applied", "interviewing", "offer"]))
            .all()
        ]
    finally:
        db.close()


def cmd_list() -> None:
    accounts = load_accounts()
    print(f"store: {store_path()}\n")
    if accounts:
        print(f"RECORDED ({len(accounts)}) — these sign in automatically:")
        for a in accounts.values():
            used = a.last_used[:10] if a.last_used else "never"
            print(f"   {a.tenant:18} {a.email:34} last used {used}")
    else:
        print("RECORDED (0) — nothing yet, so every Workday job routes to manual.")

    jobs = _workday_jobs()
    missing = missing_tenants([u for _, u in jobs])
    if not missing:
        print("\nNothing missing for the jobs currently in your queue.")
        return

    print(f"\nMISSING ({len(missing)}) — each needs a one-time signup, then it is automatic:")
    for tenant in missing:
        url = next((u for _, u in jobs if tenant_of(u) == tenant), "")
        company = next((c for c, u in jobs if tenant_of(u) == tenant), tenant)
        print(f"\n   {tenant}  ({company})")
        print(f"      register : {signup_url(url)}")
        print(f"      then run : python scripts/workday_login.py add {tenant}")


def cmd_add(tenant: str) -> None:
    tenant = tenant.strip().lower()
    if not tenant:
        print("usage: workday_login.py add <tenant>")
        return
    jobs = _workday_jobs()
    url = next((u for _, u in jobs if tenant_of(u) == tenant), "")
    if url:
        print(f"Register first (if you have not already): {signup_url(url)}\n")

    email = input("email    : ").strip()
    if not email:
        print("aborted — email is required")
        return
    password = getpass.getpass("password : ")
    if not password:
        print("aborted — password is required")
        return
    label = input("label    : ").strip() or tenant.title()

    account = save_account(tenant, email, password, label)
    print(f"\nsaved {account.tenant} ({account.email}) to {store_path()}")
    print("Workday jobs for this employer will now sign in automatically.")


def cmd_remove(tenant: str) -> None:
    print(f"removed {tenant}" if delete_account(tenant) else f"no account recorded for {tenant}")


def cmd_check(url: str) -> None:
    tenant = tenant_of(url)
    if not tenant:
        print(f"not a Workday URL: {url}")
        return
    email, _, source = credentials_for(url)
    explain = {
        "tenant": "an account recorded for this employer — will sign in",
        "default": "no account for this employer; the global WORKDAY_EMAIL would be tried "
                   "speculatively and will fail unless you happen to have registered it",
        "none": "nothing to try — this job routes to manual",
    }[source]
    print(f"tenant : {tenant}")
    print(f"source : {source} — {explain}")
    print(f"email  : {email or '(none)'}")
    if source != "tenant":
        print(f"signup : {signup_url(url)}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return
    command, rest = args[0], args[1:]
    if command == "list":
        cmd_list()
    elif command == "add" and rest:
        cmd_add(rest[0])
    elif command == "remove" and rest:
        cmd_remove(rest[0])
    elif command == "check" and rest:
        cmd_check(rest[0])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

"""
Repository health check.

Catches the classes of defect that have actually bitten this project rather
than a generic lint: modules that no longer import, dependencies that are used
but undeclared, code that is written but wired to nothing, and control
characters injected by shell heredocs (one of those silently disabled a regex
in the extension for days).

    python scripts/audit.py
"""
from __future__ import annotations

import ast
import importlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SKIP_DIRS = ("venv", "node_modules", ".next", "__pycache__", ".git")
problems: list[str] = []


def relevant(path: pathlib.Path) -> bool:
    return not any(part in SKIP_DIRS for part in path.parts)


def section(title: str) -> None:
    print(f"\n{title}")


def ok(msg: str) -> None:
    print(f"  ok    {msg}")


def bad(msg: str) -> None:
    problems.append(msg)
    print(f"  FAIL  {msg}")


# ── 1. Everything parses and imports ─────────────────────────────────────────

def check_python() -> None:
    section("Python")
    files = [f for f in ROOT.rglob("*.py") if relevant(f)]
    syntax = 0
    for f in files:
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            syntax += 1
            bad(f"syntax {f.relative_to(ROOT)}:{exc.lineno} {exc.msg}")
    if not syntax:
        ok(f"{len(files)} files parse")

    failed = 0
    for f in sorted((ROOT / "backend").rglob("*.py")):
        if not relevant(f):
            continue
        parts = list(f.relative_to(ROOT).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        module = ".".join(parts)
        if not module:
            continue
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 - reporting, not handling
            failed += 1
            bad(f"import {module}: {type(exc).__name__}: {str(exc)[:70]}")
    if not failed:
        ok("every backend module imports")


# ── 2. Declared dependencies match reality ───────────────────────────────────

THIRD_PARTY = {
    "fastapi", "uvicorn", "sqlalchemy", "playwright", "dotenv", "multipart",
    "httpx", "aiofiles", "pydantic", "pydantic_settings", "bs4", "lxml",
    "loguru", "requests", "openai", "fitz", "pylatexenc", "PyPDF2", "docx",
    "reportlab",
}
DIST_TO_MODULE = {
    "python-dotenv": "dotenv", "python-multipart": "multipart",
    "beautifulsoup4": "bs4", "pydantic-settings": "pydantic_settings",
    "pymupdf": "fitz", "python-docx": "docx",
}


def check_requirements() -> None:
    section("Dependencies")
    used = set()
    for f in (ROOT / "backend").rglob("*.py"):
        if not relevant(f):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                used.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                used.add(node.module.split(".")[0])
    used &= THIRD_PARTY

    req_file = ROOT / "backend" / "requirements.txt"
    declared = set()
    for line in req_file.read_text(encoding="utf-8").splitlines():
        name = re.split(r"[<>=!\[]", line.strip(), 1)[0].strip().lower()
        if name and not name.startswith("#"):
            declared.add(DIST_TO_MODULE.get(name, name))

    missing = sorted(m for m in used if m.lower() not in declared)
    if missing:
        bad(f"imported but undeclared in requirements.txt: {', '.join(missing)}")
    else:
        ok(f"all {len(used)} third-party imports are declared")


# ── 3. Shell-injected control characters ─────────────────────────────────────

def check_control_chars() -> None:
    section("Control characters")
    hits = 0
    for pattern in ("*.py", "*.js", "*.ts", "*.tsx", "*.json", "*.tex", "*.md"):
        for f in ROOT.rglob(pattern):
            if not relevant(f):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for i, ch in enumerate(text):
                code = ord(ch)
                if code < 9 or code in (11, 12) or 14 <= code < 32:
                    hits += 1
                    bad(f"{f.relative_to(ROOT)} has {hex(code)} near {text[max(0, i-30):i+10]!r}")
                    break
    if not hits:
        ok("no stray control characters")


# ── 4. Code that is written but reachable from nothing ───────────────────────

def check_wiring() -> None:
    section("Wiring")
    backend = "\n".join(
        f.read_text(encoding="utf-8")
        for f in (ROOT / "backend").rglob("*.py")
        if relevant(f)
    )
    for module, marker in [
        ("backend/scrapers/bigtech.py", "bigtech"),
        ("backend/autopilot/select.py", "autopilot.select"),
        ("backend/resume/tailor.py", "resume import tailor"),
        ("backend/applier/routing.py", "applier.routing"),
        ("backend/applier/workday_creds.py", "workday_creds"),
    ]:
        path = ROOT / module
        if not path.is_file():
            bad(f"{module} is referenced by the audit but missing")
            continue
        if marker in backend:
            ok(f"{module} is wired in")
        else:
            bad(f"{module} exists but nothing imports it")

    routes = json.dumps(sorted(_api_routes()))
    for prefix in ("/api/autofill", "/api/autopilot", "/api/jobs", "/api/scan"):
        if prefix in routes:
            ok(f"routes mounted: {prefix}")
        else:
            bad(f"no routes under {prefix}")


def _api_routes() -> list[str]:
    from backend.api.main import app

    return [r.path for r in app.routes if getattr(r, "path", "").startswith("/api/")]


# ── 5. Extension manifest sanity ─────────────────────────────────────────────

def check_extension() -> None:
    section("Extension")
    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
    files = [manifest["background"]["service_worker"]]
    files += manifest["content_scripts"][0]["js"]
    files.append(manifest["action"]["default_popup"])
    files += list(manifest["icons"].values())
    missing = [f for f in files if not (ROOT / "extension" / f).is_file()]
    if missing:
        bad(f"manifest references missing files: {missing}")
    else:
        ok(f"all {len(files)} manifest files exist")

    excludes = manifest["content_scripts"][0].get("exclude_matches", [])
    if any("linkedin" in e for e in excludes):
        ok("linkedin.com excluded from content scripts")
    else:
        bad("content script still runs on linkedin.com (fingerprinting risk)")


# ── 6. Secrets must never be tracked ─────────────────────────────────────────

def check_secrets() -> None:
    section("Secrets")
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for path in ("config/.env", "config/workday_accounts.json"):
        if pathlib.Path(path).name in ignored or path in ignored:
            ok(f"{path} is gitignored")
        else:
            bad(f"{path} is NOT gitignored")


def main() -> None:
    check_python()
    check_requirements()
    check_control_chars()
    check_wiring()
    check_extension()
    check_secrets()

    print()
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("Clean.")


if __name__ == "__main__":
    main()

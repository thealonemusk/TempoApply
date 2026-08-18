"""Load apply credentials from .env on each call (survives API process started before .env existed)."""
from __future__ import annotations

from pathlib import Path

from backend.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _env_value(key: str) -> str:
    path = PROJECT_ROOT / "config" / ".env"
    if not path.exists():
        path = PROJECT_ROOT / ".env"
    if not path.exists():
        return ""
    prefix = key + "="
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def workday_credentials() -> tuple[str, str]:
    email = (
        _env_value("WORKDAY_EMAIL")
        or settings.workday_email
        or settings.user_email
        or ""
    ).strip()
    password = (_env_value("WORKDAY_PASSWORD") or settings.workday_password or "").strip()
    return email, password


def linkedin_credentials() -> tuple[str, str]:
    email = (_env_value("LINKEDIN_EMAIL") or settings.linkedin_email or "").strip()
    password = (_env_value("LINKEDIN_PASSWORD") or settings.linkedin_password or "").strip()
    return email, password

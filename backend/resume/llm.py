"""
The one place that talks to a model.

Two providers, chosen explicitly by `LLM_PROVIDER` in `config/.env`:

  * blank / `openai` — `gpt_key`, `OPENAI_MODEL`, and optionally
    `OPENAI_BASE_URL` for any OpenAI-compatible server (a gateway, Ollama).
  * `gemini` — `GEMINI_API_KEY` and `GEMINI_MODEL`, sent to Google's
    OpenAI-compatible endpoint, so the same client and JSON mode serve both.

Explicit rather than "whichever key is set": both keys can be present at once
(the OpenAI key here authenticates but has no credit), and a run must never be
unclear about which provider it used.

Every call asks for JSON and returns a dict. The model is never asked to produce
LaTeX, a whole document, or a file — only sentences and lists, which the
deterministic code around it then validates and places.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Optional

from loguru import logger

from backend.config import settings

# Tailoring is worth a capable model — it is one call per application, and a
# clumsy rewrite costs an interview. Overridable via OPENAI_MODEL.
DEFAULT_MODEL = "gpt-5.4"
# gemini-2.x is closed to new keys ("no longer available to new users").
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

MAX_ATTEMPTS = 3                       # per model
# The free Gemini tier allows 5 requests a minute per model and names the wait
# ("retry in 52s"). Waiting that long is what makes a 30-job batch finish. A
# wait longer than this means a daily quota is gone — fail now, and tailoring
# falls back to its deterministic half instead of hanging for hours.
MAX_RATE_WAIT_S = 90
OVERLOAD_BACKOFF_S = (5, 15)           # 503 "high demand"; no wait is given
# A model that just exhausted its retries is skipped for this long. Without it,
# every job in a batch re-learns the outage: ~2 minutes of retries each, over an
# hour of dead waiting for 30 jobs.
COOLDOWN_S = 300
_down_until: Dict[str, float] = {}


class LLMUnavailable(RuntimeError):
    """No usable API key, or the SDK is not installed."""


def provider() -> str:
    return (getattr(settings, "llm_provider", "") or "").strip().lower() or "openai"


def api_key() -> str:
    if provider() == "gemini":
        return (getattr(settings, "gemini_api_key", "") or "").strip()
    return (getattr(settings, "gpt_key", "") or "").strip()


def model_name() -> str:
    if provider() == "gemini":
        return (getattr(settings, "gemini_model", "") or "").strip() or DEFAULT_GEMINI_MODEL
    return (getattr(settings, "openai_model", "") or "").strip() or DEFAULT_MODEL


def fallback_model() -> str:
    """
    Tried when the primary is overloaded or out of quota. Gemini's free quota is
    per model, so a second model also doubles the rate. Blank means none.
    """
    if provider() == "gemini":
        return (getattr(settings, "gemini_fallback_model", "") or "").strip()
    return ""


def base_url() -> str:
    """Where to send requests. Blank means OpenAI's own endpoint."""
    if provider() == "gemini":
        return GEMINI_BASE_URL
    return (getattr(settings, "openai_base_url", "") or "").strip().rstrip("/")


def _usable(key: str) -> bool:
    # "your_gemini_key_here" and friends are template placeholders.
    return bool(key) and not key.lower().startswith("your")


def is_available() -> bool:
    if provider() not in {"openai", "gemini"} or not _usable(api_key()):
        return False
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


def _client():
    key = api_key()
    if not _usable(key):
        name = "GEMINI_API_KEY" if provider() == "gemini" else "gpt_key"
        raise LLMUnavailable(f"No usable API key. Set {name} in config/.env.")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise LLMUnavailable("The openai package is not installed — pip install openai") from exc

    url = base_url()
    return OpenAI(api_key=key, base_url=url, max_retries=0) if url else OpenAI(api_key=key, max_retries=0)


DAILY_COOLDOWN_S = 3600


def _is_daily_quota(exc: Exception) -> bool:
    """Google names the exhausted quota, e.g. GenerateRequestsPerDayPerProjectPerModel."""
    return getattr(exc, "status_code", None) == 429 and "PerDay" in str(exc)


_RETRY_IN_RE = re.compile(r"retry in ([\d.]+)\s*s|'retryDelay':\s*'(\d+)s'", re.I)


def _wait_for(exc: Exception, attempt: int) -> Optional[float]:
    """Seconds to wait before retrying `exc`, or None if retrying is pointless."""
    status = getattr(exc, "status_code", None)
    text = str(exc)
    if status == 429:
        # A spent daily quota still says "retry in 27s" — it names the next
        # per-minute window, not when the day resets. Waiting it out retries
        # into the same wall.
        if _is_daily_quota(exc):
            return None
        m = _RETRY_IN_RE.search(text)
        wait = float(m.group(1) or m.group(2)) + 1.0 if m else 20.0
        return wait if wait <= MAX_RATE_WAIT_S else None
    if status in (500, 502, 503, 504):
        return OVERLOAD_BACKOFF_S[min(attempt, len(OVERLOAD_BACKOFF_S) - 1)]
    if status in (400, 401, 403, 404):
        return None                      # a bad request or key does not heal
    return 2.0                           # transport error, malformed JSON


def ask_json(
    system: str,
    user: str,
    *,
    model: Optional[str] = None,
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """
    One JSON-mode call, retried on transient failure with the wait the server
    asks for, then on the fallback model. Raises LLMUnavailable when every
    model is down, and callers degrade to the deterministic path.
    """
    client = _client()
    models = [m for m in dict.fromkeys([model or model_name(), fallback_model()]) if m]
    last_error: Optional[Exception] = None

    # OpenAI's reasoning models refuse `max_tokens`; several OpenAI-compatible
    # servers (Ollama, Gemini's compatibility layer) only know `max_tokens`.
    limit = (
        {"max_tokens": max_tokens} if base_url() else {"max_completion_tokens": max_tokens}
    )

    for chosen in models:
        if _down_until.get(chosen, 0.0) > time.time():
            logger.info(f"Skipping {chosen}: it failed recently and is cooling down")
            continue
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = client.chat.completions.create(
                    model=chosen,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                    **limit,
                )
                content = (response.choices[0].message.content or "").strip()
                if not content:
                    raise ValueError("empty response")
                return json.loads(content)
            except Exception as exc:  # noqa: BLE001 - retried, then surfaced
                last_error = exc
                wait = _wait_for(exc, attempt)
                final = wait is None or attempt == MAX_ATTEMPTS - 1
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{MAX_ATTEMPTS}, {provider()}/{chosen}): "
                    f"{str(exc)[:300]}" + ("" if final else f" — retrying in {wait:.0f}s")
                )
                if final:
                    # Overloaded, out of quota, or retired: sit it out, so the
                    # next job goes straight to the fallback or the offline path.
                    if getattr(exc, "status_code", None) in (404, 429, 500, 502, 503, 504):
                        pause = DAILY_COOLDOWN_S if _is_daily_quota(exc) else COOLDOWN_S
                        _down_until[chosen] = time.time() + pause
                    break
                time.sleep(wait)

    if last_error is None:
        raise LLMUnavailable(f"every {provider()} model is cooling down after recent failures")
    raise LLMUnavailable(f"{provider()} request failed: {str(last_error)[:300]}")

"""
The one place that talks to a model.

Only OpenAI is wired up: `GEMINI_API_KEY` in this project's `.env` is the
literal placeholder string and the API rejects it, whereas `gpt_key` is a
working key. The deleted `backend/ai/resume_tailor.py` also used OpenAI despite
its docstring claiming Gemini.

Every call asks for JSON and returns a dict. The model is never asked to produce
LaTeX, a whole document, or a file — only sentences and lists, which the
deterministic code around it then validates and places.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.config import settings

# Tailoring is worth a capable model — it is one call per application, and a
# clumsy rewrite costs an interview. Overridable via OPENAI_MODEL.
DEFAULT_MODEL = "gpt-5.4"
MAX_RETRIES = 2


class LLMUnavailable(RuntimeError):
    """No usable API key, or the SDK is not installed."""


def api_key() -> str:
    return (getattr(settings, "gpt_key", "") or "").strip()


def model_name() -> str:
    return (getattr(settings, "openai_model", "") or "").strip() or DEFAULT_MODEL


def is_available() -> bool:
    key = api_key()
    if not key or key.lower().startswith("your"):
        return False
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


def base_url() -> str:
    """Where to send requests. Blank means OpenAI's own endpoint."""
    return (getattr(settings, "openai_base_url", "") or "").strip().rstrip("/")


def _client():
    key = api_key()
    if not key:
        raise LLMUnavailable(
            "No API key. Set gpt_key in config/.env "
            "(GEMINI_API_KEY in this project is a placeholder and does not work)."
        )
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise LLMUnavailable("The openai package is not installed — pip install openai") from exc

    # A base URL lets any OpenAI-compatible provider serve this: a gateway, a
    # proxy, or a local runtime like Ollama, which needs no key and no account.
    url = base_url()
    return OpenAI(api_key=key, base_url=url) if url else OpenAI(api_key=key)


def ask_json(
    system: str,
    user: str,
    *,
    model: Optional[str] = None,
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """One JSON-mode call, retried on transport or parse failure."""
    client = _client()
    chosen = model or model_name()
    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=chosen,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=max_tokens,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty response")
            return json.loads(content)
        except Exception as exc:  # noqa: BLE001 - retried, then surfaced
            last_error = exc
            logger.warning(f"LLM call failed (attempt {attempt + 1}/{MAX_RETRIES + 1}): {exc}")

    raise LLMUnavailable(f"OpenAI request failed after retries: {last_error}")

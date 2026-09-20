"""
Check whether the configured AI key actually works for resume tailoring.

Put the key in `config/.env` and run this. Nothing is printed except the key's
shape (first four characters and length) — the value itself never leaves the
machine and never needs to be pasted into a chat.

    python scripts/check_ai_key.py

Keys are recognised by prefix:

    sk-proj- / sk-      OpenAI
    sk-ant-             Anthropic
    AIza                Google Gemini
    anything else       tried as OpenAI-compatible if OPENAI_BASE_URL is set

A valid key is not the same as a usable one: a key can authenticate and still
be refused for having no credit, which is exactly what happened with the key
already in this project. So this makes a real (tiny) generation call rather than
just listing models.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402

TIMEOUT = 30


def shape(key: str) -> str:
    if not key:
        return "(empty)"
    return f"{key[:4]}… ({len(key)} chars)"


def _post(url: str, payload: dict, headers: dict) -> tuple[bool, str]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        try:
            parsed = json.loads(detail)
            detail = parsed.get("error", {}).get("message", detail) if isinstance(parsed, dict) else detail
        except Exception:
            pass
        return False, f"HTTP {exc.code}: {detail}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def check_openai(key: str, model: str, url: str) -> tuple[bool, str]:
    endpoint = f"{url.rstrip('/')}/chat/completions" if url else "https://api.openai.com/v1/chat/completions"
    return _post(
        endpoint,
        {"model": model, "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
         "max_completion_tokens": 16},
        {"Authorization": f"Bearer {key}"},
    )


def check_gemini(key: str, model: str) -> tuple[bool, str]:
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    )
    return _post(endpoint, {"contents": [{"parts": [{"text": "Reply with the single word: ok"}]}]}, {})


def check_anthropic(key: str) -> tuple[bool, str]:
    return _post(
        "https://api.anthropic.com/v1/messages",
        {"model": "claude-sonnet-5", "max_tokens": 16,
         "messages": [{"role": "user", "content": "Reply with the single word: ok"}]},
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
    )


def main() -> None:
    gpt = (settings.gpt_key or "").strip()
    gem = (settings.gemini_api_key or "").strip()
    url = (getattr(settings, "openai_base_url", "") or "").strip()
    model = getattr(settings, "openai_model", "") or "gpt-5.4"

    print("configured in config/.env")
    print(f"  gpt_key         : {shape(gpt)}")
    print(f"  GEMINI_API_KEY  : {shape(gem)}")
    print(f"  OPENAI_BASE_URL : {url or '(default: api.openai.com)'}")
    print(f"  OPENAI_MODEL    : {model}")
    print()

    results = []

    for label, key in (("gpt_key", gpt), ("GEMINI_API_KEY", gem)):
        if not key or key.lower().startswith("your"):
            print(f"{label:16} SKIP  not set (or still the placeholder)")
            continue

        if key.startswith("sk-ant-"):
            ok, detail = check_anthropic(key)
            kind = "Anthropic"
        elif key.startswith("AIza"):
            ok, detail = check_gemini(key, getattr(settings, "gemini_model", "gemini-2.0-flash"))
            kind = "Gemini"
        elif key.startswith("sk-") or url:
            ok, detail = check_openai(key, model, url)
            kind = "OpenAI-compatible"
        else:
            print(f"{label:16} UNKNOWN key format — set OPENAI_BASE_URL to use it as OpenAI-compatible")
            continue

        print(f"{label:16} {'WORKS' if ok else 'FAILS'}  [{kind}]  {detail if not ok else ''}")
        results.append(ok)

    print()
    if any(results):
        print("Tailoring will rewrite bullets.")
    else:
        print("No usable key. Tailoring still compiles the PDF, audits it for ATS")
        print("problems, trims to one page and reports the keyword gap — it just")
        print("will not reword anything. See: python backend/resume/test_resume.py")


if __name__ == "__main__":
    main()

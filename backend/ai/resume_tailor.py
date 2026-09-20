"""
Resume Tailor — uses Gemini to tailor a LaTeX resume for a specific job description.
Outputs both the modified .tex text and a plain text version.
"""
import json
import re
import os
from datetime import datetime
from pathlib import Path
from google import genai
from loguru import logger

from backend.config import settings

_client = genai.Client(api_key=settings.gemini_api_key)
_MODEL = "gemini-1.5-flash"


def tailor_resume(
    jd_text: str,
    base_resume_tex: str,
    job_title: str,
    company: str,
    key_requirements: list = None,
    missing_skills: list = None,
) -> dict:
    """
    Tailor base LaTeX resume for a specific job.
    Returns dict: { tailored_tex, tailored_text, changes_summary }
    """
    key_req_str = ", ".join(key_requirements or [])
    missing_str = ", ".join(missing_skills or [])

    prompt = f"""You are an expert resume writer and ATS optimization specialist.

TASK: Tailor the following LaTeX resume for this specific job WITHOUT fabricating experience.
Only reorder, rephrase, and emphasize existing experience to match the job better.

JOB TITLE: {job_title} at {company}
KEY REQUIREMENTS: {key_req_str}
SKILLS TO EMPHASIZE (if present): {missing_str}

JOB DESCRIPTION (first 2000 chars):
{jd_text[:2000]}

BASE RESUME (LaTeX):
{base_resume_tex[:4000]}

Instructions:
1. Reorder bullet points to put most relevant experience first
2. Rephrase bullets using keywords from the JD for ATS optimization
3. Emphasize skills and technologies matching the job
4. Keep all personal info, education, and dates EXACTLY as-is
5. Do NOT add fabricated experience or skills
6. Keep it to 1 page worth of content

Respond with ONLY valid JSON:
{{
  "tailored_tex": "<complete tailored LaTeX code>",
  "changes_summary": "<2-3 sentences describing what was changed and why>",
  "top_keywords_added": ["<keyword1>", "<keyword2>"]
}}"""

    try:
        response = _client.models.generate_content(model=_MODEL, contents=prompt)
        text = response.text.strip()
        # Extract JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            tailored_tex = result.get("tailored_tex", base_resume_tex)
            return {
                "tailored_tex": tailored_tex,
                "changes_summary": result.get("changes_summary", ""),
                "top_keywords_added": result.get("top_keywords_added", []),
            }
    except Exception as e:
        logger.error(f"Resume tailoring failed: {e}")

    return {
        "tailored_tex": base_resume_tex,
        "changes_summary": "Tailoring failed, using base resume",
        "top_keywords_added": [],
    }


def save_tailored_resume(tailored_tex: str, job_id: str, company: str) -> str:
    """Save tailored .tex to resumes/tailored/ and return the path."""
    safe_company = re.sub(r'[^\w\s-]', '', company).strip().replace(' ', '_')
    filename = f"{safe_company}_{job_id[:8]}.tex"
    output_dir = Path(settings.base_resume_path).parent.parent / "tailored"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_text(tailored_tex, encoding="utf-8")
    logger.info(f"💾 Tailored resume saved: {output_path}")
    return str(output_path)

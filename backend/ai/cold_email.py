"""
Cold Email & LinkedIn Message Generator — uses Gemini to write
personalized, concise outreach messages for each job application.
"""
import json
import re
from openai import OpenAI
from loguru import logger

from backend.config import settings

_client = OpenAI(api_key=settings.gpt_key)
_MODEL = "gpt-4o"


def generate_cold_email(
    job_title: str,
    company: str,
    jd_text: str,
    recruiter_name: str = "",
    candidate_name: str = "",
    fit_reason: str = "",
) -> str:
    """Generate a personalized cold email to a recruiter."""
    candidate = candidate_name or settings.user_full_name
    recruiter_greeting = f"Hi {recruiter_name}," if recruiter_name else "Hi there,"

    prompt = f"""You are a professional career coach writing a cold email.

CANDIDATE: {candidate}
ROLE APPLYING FOR: {job_title} at {company}
WHY THEY'RE A FIT: {fit_reason}
JOB DESCRIPTION (excerpt):
{jd_text[:1500]}

Write a compelling cold email to the recruiter. Rules:
- Start with: {recruiter_greeting}
- Keep it under 150 words
- Mention 1-2 specific things about {company} that excite the candidate
- Highlight 1-2 concrete achievements/skills relevant to the role
- End with a clear CTA (asking for a 15-min call or to review their profile)
- Tone: professional but warm and confident
- Do NOT use clichés like "I hope this email finds you well" or "I'm reaching out because"

Output ONLY the email body text, no subject line, no JSON."""

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Cold email generation failed: {e}")
        return f"""{recruiter_greeting}

I'm {candidate}, a software engineer passionate about building impactful products. I came across the {job_title} role at {company} and was immediately drawn to your work.

My background aligns well with what you're looking for — I'd love to share how I can contribute to your team.

Would you be open to a quick 15-minute call this week?

Best regards,
{candidate}"""


def generate_linkedin_message(
    job_title: str,
    company: str,
    recruiter_name: str = "",
    candidate_name: str = "",
    fit_reason: str = "",
) -> str:
    """Generate a short LinkedIn InMail/DM (under 300 chars for connection request)."""
    candidate = candidate_name or settings.user_full_name
    recruiter_greeting = f"Hi {recruiter_name}!" if recruiter_name else "Hi!"

    prompt = f"""Write a LinkedIn connection request message (MAX 250 characters).

CANDIDATE: {candidate}
ROLE: {job_title} at {company}
WHY THEY FIT: {fit_reason}

Rules:
- Start with {recruiter_greeting}
- Mention the specific role
- Be friendly and direct
- No emojis
- MAX 250 characters total

Output ONLY the message text."""

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        msg = response.choices[0].message.content.strip()
        return msg[:300]  # Safety trim
    except Exception as e:
        logger.error(f"LinkedIn message generation failed: {e}")
        return f"{recruiter_greeting} I noticed the {job_title} role at {company}. I'm {candidate}, a software engineer excited about your work. Happy to connect!"


def generate_cover_letter(
    job_title: str,
    company: str,
    jd_text: str,
    base_resume_text: str,
    candidate_name: str = "",
) -> str:
    """Generate a full cover letter for a job application."""
    candidate = candidate_name or settings.user_full_name

    prompt = f"""Write a professional cover letter for:
CANDIDATE: {candidate}
ROLE: {job_title} at {company}

CANDIDATE RESUME SUMMARY:
{base_resume_text[:2000]}

JOB DESCRIPTION:
{jd_text[:1500]}

Rules:
- 3 short paragraphs max
- Opening: why you want THIS company specifically
- Middle: 2 concrete examples from resume matching the JD
- Closing: enthusiasm + CTA
- Professional but not stiff
- 200-250 words

Output ONLY the letter body (no "Dear Hiring Manager" header needed)."""

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Cover letter generation failed: {e}")
        return ""

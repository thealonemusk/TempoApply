"""
Job Analyzer — uses Gemini to score job fit, detect seniority, and
identify missing skills relative to the candidate's base resume.
"""
import json
import re
from google import genai
from loguru import logger

from backend.config import settings

_client = genai.Client(api_key=settings.gemini_api_key)
_MODEL = "gemini-1.5-flash"


def analyze_jd(jd_text: str, base_resume_text: str, job_title: str = "") -> dict:
    """
    Score how well this job matches the candidate's profile.
    Returns a dict with:
        score (0-100), fit_reason, missing_skills (list),
        seniority_level, is_engineering_role, key_requirements (list)
    """
    prompt = f"""You are an expert technical recruiter and career coach.

CANDIDATE RESUME:
{base_resume_text[:3000]}

JOB TITLE: {job_title}
JOB DESCRIPTION:
{jd_text[:3000]}

Analyze the fit between this candidate and job. Respond ONLY with valid JSON:
{{
  "score": <integer 0-100, how well candidate fits this role>,
  "fit_reason": "<2-3 sentence summary of why this is or isn't a good fit>",
  "missing_skills": ["<skill1>", "<skill2>"],
  "key_requirements": ["<requirement1>", "<requirement2>", "<requirement3>"],
  "seniority_level": "<junior|mid|senior|staff|lead|manager>",
  "is_engineering_role": <true|false>,
  "recommended_apply": <true|false>
}}

Score guidelines:
- 80-100: Excellent match, most requirements met
- 60-79: Good match, apply with tailored resume
- 40-59: Partial match, skill gaps present
- 0-39: Poor match, not recommended
"""

    try:
        response = _client.models.generate_content(model=_MODEL, contents=prompt)
        text = response.text.strip()
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            return result
    except Exception as e:
        logger.error(f"JD analysis failed: {e}")

    return {
        "score": 0,
        "fit_reason": "Analysis failed",
        "missing_skills": [],
        "key_requirements": [],
        "seniority_level": "mid",
        "is_engineering_role": True,
        "recommended_apply": False,
    }


def generate_search_queries(base_resume_text: str, max_queries: int = 3) -> list[str]:
    """
    Read the user's resume and generate highly targeted job titles
    to be used in job board search queries (e.g., "Senior React Developer").
    """
    if not base_resume_text:
        return settings.target_roles_list

    prompt = f"""You are an expert technical recruiter. Based on the following candidate resume,
generate up to {max_queries} highly optimal and specific job titles that this candidate is perfectly suited for.
These will be plugged directly into LinkedIn/Indeed search bars.
Keep them concise (e.g., "Frontend Developer", "Senior Python Backend Engineer").

CANDIDATE RESUME:
{base_resume_text[:4000]}

Respond ONLY with valid JSON in this format:
{{
  "queries": ["title 1", "title 2", "title 3"]
}}
"""
    try:
        response = _client.models.generate_content(model=_MODEL, contents=prompt)
        text = response.text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            if "queries" in result and isinstance(result["queries"], list):
                logger.info(f"Dynamically targeted job roles: {result['queries']}")
                return result["queries"][:max_queries]
    except Exception as e:
        logger.error(f"Failed to generate search queries: {e}")

    # Fallback to static settings
    return settings.target_roles_list


def batch_filter_jobs(jobs: list, base_resume_text: str) -> list:
    """
    Quick-filter a list of job dicts (with title + jd_text) using Gemini.
    Returns jobs with analysis fields populated, sorted by score desc.
    """
    results = []
    for job in jobs:
        analysis = analyze_jd(
            jd_text=job.get("jd_text", ""),
            base_resume_text=base_resume_text,
            job_title=job.get("title", ""),
        )
        job.update(analysis)
        if analysis.get("is_engineering_role", True) and analysis.get("score", 0) >= settings.min_relevance_score:
            results.append(job)
            logger.info(f"✅ [{analysis['score']}/100] {job.get('company')} - {job.get('title')}")
        else:
            logger.info(f"❌ [{analysis.get('score', 0)}/100] Filtered out: {job.get('company')} - {job.get('title')}")
    
    return sorted(results, key=lambda x: x.get("score", 0), reverse=True)

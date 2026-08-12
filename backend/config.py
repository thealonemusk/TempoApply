from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os
from pathlib import Path

# Load .env from config directory or root
env_path = Path(__file__).parent.parent / "config" / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    # AI
    gemini_api_key: str = ""

    # Platform credentials
    linkedin_email: str = ""
    linkedin_password: str = ""
    indeed_email: str = ""
    indeed_password: str = ""
    naukri_email: str = ""
    naukri_password: str = ""
    instahyre_email: str = ""
    instahyre_password: str = ""

    # User profile
    user_full_name: str = "Ashutosh Jha"
    user_phone: str = ""
    user_location: str = "Bengaluru, India"
    user_github: str = ""
    user_linkedin_url: str = ""
    user_portfolio: str = ""

    # Job preferences
    target_roles: str = "Software Engineer,Backend Engineer"
    experience_years: int = 3
    preferred_locations: str = "Bengaluru,Remote"
    min_relevance_score: int = 60
    excluded_companies: str = ""

    # App
    base_resume_path: str = "resumes/base_resume.tex"
    database_url: str = "sqlite:///./tempoapply.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = str(env_path)
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def target_roles_list(self) -> List[str]:
        return [r.strip() for r in self.target_roles.split(",")]

    @property
    def preferred_locations_list(self) -> List[str]:
        return [l.strip() for l in self.preferred_locations.split(",")]

    @property
    def excluded_companies_list(self) -> List[str]:
        if not self.excluded_companies:
            return []
        return [c.strip() for c in self.excluded_companies.split(",")]


settings = Settings()

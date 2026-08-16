from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, ForeignKey, Boolean, text
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from backend.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    platform = Column(String, nullable=False)  # linkedin, indeed, naukri, instahyre, manual
    url = Column(String, unique=True, nullable=False)
    location = Column(String, default="")
    experience_required = Column(String, default="")
    salary_range = Column(String, default="")
    jd_text = Column(Text, default="")
    # AI analysis results
    relevance_score = Column(Float, default=0.0)
    fit_reason = Column(Text, default="")
    missing_skills = Column(Text, default="")  # JSON list
    seniority_level = Column(String, default="")
    is_engineering_role = Column(Boolean, default=True)
    # Status tracking
    status = Column(String, default="discovered")  # discovered, scored, tailored, applied, interviewing, rejected, offer
    easy_apply = Column(Boolean, default=False)
    recruiter_name = Column(String, default="")
    recruiter_profile = Column(String, default="")
    ats_type = Column(String, default="")  # greenhouse, lever, workday, custom, unknown
    apply_status = Column(String, default="")  # queued, applying, applied, failed, needs_review, skipped
    apply_error = Column(Text, default="")
    # Timestamps
    discovered_at = Column(DateTime, default=func.now())
    visited_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())

    application = relationship("Application", back_populates="job", uselist=False)


class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    tailored_resume_path = Column(String, default="")
    tailored_resume_text = Column(Text, default="")
    cold_email = Column(Text, default="")
    linkedin_message = Column(Text, default="")
    cover_letter = Column(Text, default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=func.now())

    job = relationship("Job", back_populates="application")


class BaseResume(Base):
    __tablename__ = "base_resumes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    content_text = Column(Text, default="")  # parsed LaTeX text
    is_active = Column(Boolean, default=True)
    uploaded_at = Column(DateTime, default=func.now())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_db()
    print("Database initialized (SQLite)")


def _migrate_db():
    """Add columns to existing SQLite DBs without Alembic."""
    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info(jobs)")).fetchall()
        col_names = {row[1] for row in cols}
        if "visited_at" not in col_names:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN visited_at DATETIME"))
            conn.commit()
        extras = {
            "ats_type": "VARCHAR DEFAULT ''",
            "apply_status": "VARCHAR DEFAULT ''",
            "apply_error": "TEXT DEFAULT ''",
        }
        for name, ddl in extras.items():
            if name not in col_names:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {ddl}"))
                conn.commit()

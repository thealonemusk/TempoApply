export type JobStatus =
  | 'discovered'
  | 'scored'
  | 'tailored'
  | 'applied'
  | 'interviewing'
  | 'rejected'
  | 'offer'
  | 'ignored';

/** How a posting can be applied to. Mirrors backend/applier/ats.py. */
export type ApplyMethod =
  | 'greenhouse'
  | 'lever'
  | 'workday'
  | 'ashby'
  | 'linkedin_easy'
  | 'manual';

/** Durable per-job apply outcome stored on the Job row. */
export type ApplyStatusValue =
  | ''
  | 'queued'
  | 'running'
  | 'applied'
  | 'needs_review'
  | 'failed'
  | 'skipped';

export interface Job {
  id: string;
  title: string;
  company: string;
  platform: string;
  url: string;
  location: string;
  experience_required: string;
  salary_range: string;
  relevance_score: number;
  fit_reason: string;
  missing_skills: string;
  seniority_level: string;
  is_engineering_role: boolean;
  easy_apply: boolean;
  recruiter_name: string;
  recruiter_profile: string;
  status: JobStatus;
  discovered_at: string | null;
  visited_at: string | null;
  applied_at: string | null;
  ats_type: string;
  apply_url: string;
  apply_status: ApplyStatusValue;
  apply_error: string;
  apply_method: ApplyMethod;
  auto_appliable: boolean;
}

export interface Analytics {
  total_jobs: number;
  by_status: Record<string, number>;
  by_platform: Record<string, number>;
  by_apply_status: Record<string, number>;
  by_ats: Record<string, number>;
  top_companies: { company: string; score: number }[];
}

export interface SettingsData {
  target_roles: string[];
  experience_years: number;
  preferred_locations: string[];
  min_relevance_score: number;
  user_full_name: string;
  excluded_companies: string[];
  has_gemini_key: boolean;
  has_linkedin: boolean;
  has_naukri: boolean;
  has_indeed: boolean;
  has_instahyre: boolean;
  has_workday: boolean;
  supported_platforms: string[];
  default_concurrency: number;
  max_concurrency: number;
  job_freshness_hours: number;
}

export interface Education {
  school: string;
  degree: string;
  major: string;
  start_year: string;
  end_year: string;
}

export interface ApplicantProfile {
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  city: string;
  state: string;
  country: string;
  postal_code: string;
  address_line1: string;
  address_line2: string;
  linkedin: string;
  github: string;
  portfolio: string;
  current_title: string;
  current_company: string;
  years_experience: string;
  notice_period: string;
  earliest_start: string;
  salary_expectation: string;
  authorized_to_work: boolean;
  require_sponsorship: boolean;
  how_heard: string;
  skills: string;
  cover_letter_template: string;
  auto_submit: boolean;
  education: Education[];
  missing: string[];
  has_resume: boolean;
  ready_to_apply: boolean;
}

/** Options for starting an apply run. */
export interface ApplyOptions {
  job_ids?: string[] | null;
  auto_submit?: boolean;
  headless?: boolean;
  concurrency?: number;
  job_timeout_sec?: number;
  skip_unsupported?: boolean;
}

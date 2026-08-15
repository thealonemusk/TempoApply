export type JobStatus =
  | 'discovered'
  | 'scored'
  | 'tailored'
  | 'applied'
  | 'interviewing'
  | 'rejected'
  | 'offer'
  | 'ignored';

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
}

export interface Analytics {
  total_jobs: number;
  by_status: Record<string, number>;
  by_platform: Record<string, number>;
  top_companies: { company: string; score: number }[];
}

export interface SettingsData {
  target_roles: string[];
  experience_years: number;
  preferred_locations: string[];
  min_relevance_score: number;
  user_full_name: string;
  has_gemini_key: boolean;
  has_linkedin: boolean;
  has_naukri: boolean;
  has_indeed: boolean;
  has_instahyre: boolean;
  supported_platforms: string[];
  excluded_companies: string[];
}

export interface ScanStatus {
  running: boolean;
  last_result: Record<string, unknown> | null;
}

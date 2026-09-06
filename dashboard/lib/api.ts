import type {
  Analytics,
  ApplicantProfile,
  ApplyOptions,
  Job,
  SettingsData,
} from './types';
import type { RunKind, RunSnapshot } from './runs';
import { DEFAULT_SCAN_PLATFORMS } from './platforms';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Thrown for any non-2xx response, carrying the backend's `detail` when present. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(
      `Cannot reach the TempoApply API at ${API_BASE}. Is the backend running?`,
      0,
    );
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') message = body.detail;
    } catch {
      // keep the fallback message
    }
    throw new ApiError(message, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  // ── jobs ──────────────────────────────────────────────────────────────────
  getJobs: () => request<Job[]>('/api/jobs'),

  updateJobStatus: (id: string, status: string) =>
    request<{ success: boolean }>(`/api/jobs/${id}/status`, {
      ...json({ status }),
      method: 'PATCH',
    }),

  markJobVisited: (id: string) =>
    request<{ success: boolean; visited_at: string }>(`/api/jobs/${id}/visit`, {
      method: 'POST',
    }),

  resetJobApply: (id: string) =>
    request<{ success: boolean }>(`/api/jobs/${id}/reset-apply`, { method: 'POST' }),

  deleteJob: (id: string) =>
    request<{ success: boolean }>(`/api/jobs/${id}`, { method: 'DELETE' }),

  addManualJob: (job: {
    title: string;
    company: string;
    url: string;
    jd_text: string;
    location?: string;
  }) => request<{ job_id: string }>('/api/jobs/manual', json(job)),

  clearDiscoveredJobs: () =>
    request<{ deleted_count: number }>('/api/jobs/clear', { method: 'DELETE' }),

  purgeExperiencedJobs: () =>
    request<{ purged_count: number }>('/api/jobs/purge-experienced', { method: 'POST' }),

  purgeStaleJobs: () =>
    request<{ purged_count: number }>('/api/jobs/purge-stale', { method: 'POST' }),

  backfillAts: () =>
    request<{ updated: number }>('/api/jobs/backfill-ats', { method: 'POST' }),

  resolveApplyUrls: (limit = 200) =>
    request<{ checked: number; resolved: number }>(
      `/api/jobs/resolve-apply-urls?limit=${limit}`,
      { method: 'POST' },
    ),

  // ── runs ──────────────────────────────────────────────────────────────────
  getRun: (kind: RunKind) => request<RunSnapshot>(`/api/${kind}/run`),

  streamUrl: (kind: RunKind) => `${API_BASE}/api/${kind}/stream`,

  screenshotUrl: (jobId: string) => `${API_BASE}/api/apply/screenshot/${jobId}`,

  // ── scan ──────────────────────────────────────────────────────────────────
  startScan: (platforms = DEFAULT_SCAN_PLATFORMS, maxJobs = 400) =>
    request<{ message: string }>(
      '/api/scan',
      json({ platforms, max_jobs_per_platform: maxJobs, headless: true }),
    ),

  stopScan: () =>
    request<{ message: string; running: boolean }>('/api/scan/stop', { method: 'POST' }),

  // ── apply ─────────────────────────────────────────────────────────────────
  startApply: (options: ApplyOptions = {}) =>
    request<{ message: string; running: boolean }>(
      '/api/apply',
      json({
        job_ids: options.job_ids ?? null,
        auto_submit: options.auto_submit ?? true,
        headless: options.headless ?? false,
        concurrency: options.concurrency ?? 2,
        job_timeout_sec: options.job_timeout_sec ?? 240,
        skip_unsupported: options.skip_unsupported ?? true,
      }),
    ),

  stopApply: () =>
    request<{ message: string; running: boolean }>('/api/apply/stop', { method: 'POST' }),

  applyJob: (id: string) =>
    request<{ message: string; running: boolean }>(`/api/jobs/${id}/apply`, {
      method: 'POST',
    }),

  // ── analytics, settings, profile ──────────────────────────────────────────
  getAnalytics: () => request<Analytics>('/api/analytics'),

  getSettings: () => request<SettingsData>('/api/settings'),

  saveSettings: (payload: Record<string, unknown>) =>
    request<{ success: boolean }>('/api/settings', json(payload)),

  getProfile: () => request<ApplicantProfile>('/api/profile'),

  saveProfile: (payload: Record<string, unknown>) =>
    request<ApplicantProfile>('/api/profile', { ...json(payload), method: 'PUT' }),

  uploadResume: async (file: File) => {
    const body = new FormData();
    body.append('file', file);
    const res = await fetch(`${API_BASE}/api/profile/resume`, { method: 'POST', body });
    if (!res.ok) throw new ApiError(`Resume upload failed (${res.status})`, res.status);
    return res.json() as Promise<{ success: boolean; resume_path: string }>;
  },
};

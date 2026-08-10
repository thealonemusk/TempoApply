import type { Analytics, Job, ScanStatus, SettingsData } from './types';
import { DEFAULT_SCAN_PLATFORMS } from './platforms';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getJobs: () => request<Job[]>('/api/jobs'),

  getScanStatus: () => request<ScanStatus>('/api/scan/status'),

  startScan: (platforms = DEFAULT_SCAN_PLATFORMS, maxJobs = 25) =>
    request<{ message: string }>('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platforms,
        max_jobs_per_platform: maxJobs,
        headless: true,
      }),
    }),

  updateJobStatus: (id: string, status: string) =>
    request<{ success: boolean }>(`/api/jobs/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    }),

  addManualJob: (job: {
    title: string;
    company: string;
    url: string;
    jd_text: string;
    location?: string;
  }) =>
    request('/api/jobs/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(job),
    }),

  clearDiscoveredJobs: () =>
    request<{ deleted_count: number }>('/api/jobs/clear', { method: 'DELETE' }),

  purgeExperiencedJobs: () =>
    request<{ purged_count: number }>('/api/jobs/purge-experienced', { method: 'POST' }),

  getAnalytics: () => request<Analytics>('/api/analytics'),

  getSettings: () => request<SettingsData>('/api/settings'),

  saveSettings: (payload: Record<string, unknown>) =>
    request<{ success: boolean }>('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
};

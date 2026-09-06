export const PLATFORM_LABELS: Record<string, string> = {
  linkedin: 'LinkedIn',
  indeed: 'Indeed',
  naukri: 'Naukri',
  instahyre: 'InstaHyre',
  wellfound: 'Wellfound',
  company_careers: 'Career site',
  manual: 'Manual',
};

/**
 * Chart series colours. Chosen to stay legible on both the light and dark
 * canvas rather than matching each platform's brand colour, which is what the
 * previous palette did (LinkedIn navy vanished on the dark background).
 */
export const PLATFORM_COLORS: Record<string, string> = {
  linkedin: '#4f7cf0',
  indeed: '#6f6ae0',
  naukri: '#e07a4a',
  instahyre: '#8b6ae0',
  wellfound: '#7a8290',
  company_careers: '#2ea36a',
  manual: '#8b8e9c',
};

export const DEFAULT_SCAN_PLATFORMS = ['linkedin', 'naukri', 'company_careers'];

export function platformLabel(key: string): string {
  return PLATFORM_LABELS[key] || key.replace(/_/g, ' ');
}

export const ATS_LABELS: Record<string, string> = {
  greenhouse: 'Greenhouse',
  lever: 'Lever',
  workday: 'Workday',
  ashby: 'Ashby',
  custom: 'Custom form',
  unknown: 'Unknown',
};

export function atsLabel(key: string): string {
  if (!key) return '';
  return ATS_LABELS[key] || key;
}

export const STATUS_COLORS: Record<string, string> = {
  discovered: '#8b8e9c',
  scored: '#4f7cf0',
  tailored: '#7c6ae0',
  applied: '#2ea36a',
  interviewing: '#d99a3d',
  rejected: '#d1544d',
  offer: '#e0b83d',
  ignored: '#6c7280',
};

/** Relative time, e.g. "3h ago". Falls back to a date past a week. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days <= 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Wall-clock duration between two ISO timestamps, for run and job timing. */
export function duration(from: string | null, to: string | null): string {
  if (!from) return '—';
  const start = new Date(from).getTime();
  const end = to ? new Date(to).getTime() : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return '—';
  const secs = Math.max(0, Math.round((end - start) / 1000));
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const rem = secs % 60;
  if (mins < 60) return rem ? `${mins}m ${rem}s` : `${mins}m`;
  const hours = Math.floor(mins / 60);
  return `${hours}h ${mins % 60}m`;
}

export const PLATFORM_LABELS: Record<string, string> = {
  linkedin: 'LinkedIn',
  indeed: 'Indeed',
  naukri: 'Naukri',
  instahyre: 'InstaHyre',
  wellfound: 'Wellfound',
  company_careers: 'Direct',
  manual: 'Manual',
};

export const PLATFORM_COLORS: Record<string, string> = {
  linkedin: '#0077B5',
  indeed: '#2164F3',
  naukri: '#FF7555',
  instahyre: '#6C5CE7',
  wellfound: '#000000',
  company_careers: '#34C759',
  manual: '#8E8E93',
};

export const DEFAULT_SCAN_PLATFORMS = [
  'linkedin',
  'naukri',
  'company_careers',
];

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

import clsx from 'clsx';
import { Zap, Hand } from 'lucide-react';
import { atsLabel, platformLabel } from '@/lib/platforms';
import type { ApplyMethod, ApplyStatusValue } from '@/lib/types';
import type { JobRunState } from '@/lib/runs';

type Tone = 'neutral' | 'accent' | 'ok' | 'warn' | 'danger' | 'info';

const TONES: Record<Tone, string> = {
  neutral: 'bg-[var(--neutral-soft)] text-[var(--ink-muted)]',
  accent: 'bg-[var(--accent-soft)] text-[var(--accent)]',
  ok: 'bg-[var(--ok-soft)] text-[var(--ok)]',
  warn: 'bg-[var(--warn-soft)] text-[var(--warn)]',
  danger: 'bg-[var(--danger-soft)] text-[var(--danger)]',
  info: 'bg-[var(--info-soft)] text-[var(--info)]',
};

export function Chip({
  children,
  tone = 'neutral',
  className,
  mono = false,
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
  mono?: boolean;
}) {
  return (
    <span
      className={clsx(
        'inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium leading-tight',
        TONES[tone],
        mono && 'mono',
        className,
      )}
    >
      {children}
    </span>
  );
}

export function PlatformBadge({ platform }: { platform: string }) {
  return (
    <span className="inline-flex shrink-0 items-center rounded-md border border-[var(--line)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--ink-muted)]">
      {platformLabel(platform)}
    </span>
  );
}

export function AtsBadge({ ats }: { ats?: string }) {
  if (!ats || ats === 'unknown') return null;
  return <Chip tone="neutral">{atsLabel(ats)}</Chip>;
}

/**
 * The most important signal in the app: can auto-apply actually reach a form?
 * Most aggregator postings cannot, and saying so up front is more useful than
 * letting a run discover it one timeout at a time.
 */
const METHOD_LABELS: Record<ApplyMethod, string> = {
  greenhouse: 'Greenhouse',
  lever: 'Lever',
  workday: 'Workday',
  ashby: 'Ashby',
  linkedin_easy: 'Easy Apply',
  manual: 'Manual only',
};

export function ApplyMethodBadge({
  method,
  auto,
}: {
  method: ApplyMethod;
  auto: boolean;
}) {
  return (
    <Chip
      tone={auto ? 'accent' : 'neutral'}
      className={auto ? '' : 'opacity-80'}
    >
      {auto ? <Zap className="h-2.5 w-2.5" /> : <Hand className="h-2.5 w-2.5" />}
      {METHOD_LABELS[method] ?? method}
    </Chip>
  );
}

export function ScoreBadge({ score }: { score: number }) {
  const value = Math.round(score || 0);
  const tone: Tone = value >= 90 ? 'ok' : value >= 70 ? 'info' : 'neutral';
  return (
    <span
      className={clsx(
        'mono inline-flex min-w-[2.25rem] justify-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold',
        TONES[tone],
      )}
    >
      {value}
    </span>
  );
}

const APPLY_STATUS: Record<Exclude<ApplyStatusValue, ''>, { label: string; tone: Tone }> = {
  queued: { label: 'Queued', tone: 'neutral' },
  running: { label: 'Applying', tone: 'info' },
  applied: { label: 'Applied', tone: 'ok' },
  needs_review: { label: 'Needs review', tone: 'warn' },
  failed: { label: 'Failed', tone: 'danger' },
  skipped: { label: 'Skipped', tone: 'neutral' },
};

export function ApplyStatusBadge({ status }: { status?: ApplyStatusValue | string }) {
  if (!status) return null;
  const entry = APPLY_STATUS[status as Exclude<ApplyStatusValue, ''>];
  if (!entry) return <Chip>{String(status).replace(/_/g, ' ')}</Chip>;
  return (
    <Chip tone={entry.tone} className={status === 'running' ? 'anim-pulse' : undefined}>
      {entry.label}
    </Chip>
  );
}

const RUN_STATE: Record<JobRunState, { label: string; tone: Tone }> = {
  queued: { label: 'Queued', tone: 'neutral' },
  running: { label: 'Applying', tone: 'info' },
  applied: { label: 'Applied', tone: 'ok' },
  needs_review: { label: 'Needs review', tone: 'warn' },
  failed: { label: 'Failed', tone: 'danger' },
  skipped: { label: 'Skipped', tone: 'neutral' },
};

export function RunStateBadge({ state }: { state: JobRunState }) {
  const entry = RUN_STATE[state] ?? RUN_STATE.queued;
  return (
    <Chip tone={entry.tone} className={state === 'running' ? 'anim-pulse' : undefined}>
      {entry.label}
    </Chip>
  );
}

export function VisitedBadge() {
  return <Chip tone="neutral">Visited</Chip>;
}

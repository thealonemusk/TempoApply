import clsx from 'clsx';
import { atsLabel, platformLabel } from '@/lib/platforms';

export function PlatformBadge({ platform }: { platform: string }) {
  return (
    <span className="inline-flex items-center rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-2 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
      {platformLabel(platform)}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center rounded-lg bg-[var(--surface-2)] px-2 py-0.5 text-xs font-medium capitalize text-[var(--text-secondary)]">
      {status}
    </span>
  );
}

export function ScoreBadge({ score }: { score: number }) {
  return (
    <span
      className={clsx(
        'inline-flex min-w-[2rem] items-center justify-center rounded-lg px-2 py-0.5 text-xs font-semibold tabular-nums',
        score >= 75
          ? 'bg-[var(--success-bg)] text-[var(--success)]'
          : 'bg-[var(--surface-2)] text-[var(--text-muted)]',
      )}
    >
      {Math.round(score)}
    </span>
  );
}

export function VisitedBadge() {
  return (
    <span className="inline-flex items-center rounded-lg bg-[var(--surface-3)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
      Visited
    </span>
  );
}

export function AtsBadge({ ats }: { ats?: string }) {
  if (!ats || ats === 'unknown') return null;
  return (
    <span className="inline-flex items-center rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-muted)]">
      {atsLabel(ats)}
    </span>
  );
}

export function ApplyStatusBadge({ status }: { status?: string }) {
  if (!status) return null;
  const tone =
    status === 'applied'
      ? 'bg-[var(--success-bg)] text-[var(--success)]'
      : status === 'failed'
        ? 'bg-[var(--danger-bg)] text-[var(--danger)]'
        : status === 'needs_review' || status === 'applying' || status === 'queued'
          ? 'bg-[var(--surface-2)] text-[var(--text-secondary)]'
          : 'bg-[var(--surface-2)] text-[var(--text-muted)]';
  return (
    <span className={clsx('inline-flex items-center rounded-lg px-2 py-0.5 text-[10px] font-semibold capitalize', tone)}>
      {status.replace('_', ' ')}
    </span>
  );
}

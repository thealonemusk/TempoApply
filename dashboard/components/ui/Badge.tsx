import clsx from 'clsx';
import { platformLabel } from '@/lib/platforms';

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

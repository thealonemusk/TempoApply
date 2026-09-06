'use client';

import { useState } from 'react';
import clsx from 'clsx';
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Check,
  ExternalLink,
  Image as ImageIcon,
  Loader2,
  Minus,
} from 'lucide-react';
import { api } from '@/lib/api';
import { duration } from '@/lib/platforms';
import { STEP_LABELS, type JobProgress, type RunStep } from '@/lib/runs';
import { RunStateBadge, AtsBadge } from '@/components/ui/Badge';

const STATE_ICON = {
  applied: Check,
  needs_review: AlertTriangle,
  failed: AlertTriangle,
  skipped: Minus,
  running: Loader2,
  queued: Minus,
} as const;

/**
 * One job's attempt, expandable into its step trace.
 *
 * The step trace is the point of the whole run view: when an apply fails you
 * want to know *where* — did it reach the ATS, sign in, fill anything, find a
 * submit button — not just that it failed.
 */
export function RunJobRow({ job, defaultOpen = false }: { job: JobProgress; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const Icon = STATE_ICON[job.state] ?? Minus;
  const hasSteps = job.steps.length > 0;

  return (
    <div className="border-b border-[var(--line)] last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-[var(--surface-hover)]"
      >
        <span className="mt-0.5 shrink-0 text-[var(--ink-subtle)]">
          {hasSteps ? (
            open ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )
          ) : (
            <span className="block h-3.5 w-3.5" />
          )}
        </span>

        <span
          className={clsx(
            'mt-0.5 shrink-0',
            job.state === 'applied' && 'text-[var(--ok)]',
            job.state === 'failed' && 'text-[var(--danger)]',
            job.state === 'needs_review' && 'text-[var(--warn)]',
            job.state === 'running' && 'text-[var(--accent)]',
            (job.state === 'queued' || job.state === 'skipped') && 'text-[var(--ink-subtle)]',
          )}
        >
          <Icon className={clsx('h-3.5 w-3.5', job.state === 'running' && 'animate-spin')} />
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="truncate text-[13px] font-medium text-[var(--ink)]">{job.title}</span>
            <RunStateBadge state={job.state} />
            <AtsBadge ats={job.ats} />
          </span>
          <span className="mt-0.5 block truncate text-[11px] text-[var(--ink-muted)]">
            {job.company}
            {job.started_at && ` · ${duration(job.started_at, job.finished_at)}`}
            {hasSteps && ` · ${job.steps.length} step${job.steps.length === 1 ? '' : 's'}`}
          </span>
          {job.message && (
            <span
              className={clsx(
                'mt-1 block text-[11px] leading-snug',
                job.state === 'applied' ? 'text-[var(--ok)]' : 'text-[var(--ink-muted)]',
              )}
            >
              {job.message}
            </span>
          )}
        </span>

        <span className="flex shrink-0 items-center gap-1">
          {job.screenshot && (
            <a
              href={api.screenshotUrl(job.job_id)}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              title="Screenshot"
              className="inline-grid h-7 w-7 place-items-center rounded-md text-[var(--ink-subtle)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
            >
              <ImageIcon className="h-3.5 w-3.5" />
            </a>
          )}
          {(job.final_url || job.url) && (
            <a
              href={job.final_url || job.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              title="Open posting"
              className="inline-grid h-7 w-7 place-items-center rounded-md text-[var(--ink-subtle)] hover:bg-[var(--surface-hover)] hover:text-[var(--accent)]"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </span>
      </button>

      {open && hasSteps && (
        <ol className="space-y-1 border-t border-[var(--line)] bg-[var(--surface-sunken)] px-3 py-2.5 pl-10">
          {job.steps.map((step, i) => (
            <StepRow key={i} step={step} />
          ))}
        </ol>
      )}
    </div>
  );
}

function StepRow({ step }: { step: RunStep }) {
  const time = new Date(step.ts);
  const stamp = Number.isNaN(time.getTime())
    ? ''
    : time.toLocaleTimeString(undefined, { hour12: false });

  return (
    <li className="flex items-start gap-2.5 text-[11px] leading-snug">
      <span className="mono shrink-0 text-[var(--ink-subtle)]">{stamp}</span>
      <span
        className={clsx(
          'shrink-0 font-medium',
          step.ok === true && 'text-[var(--ok)]',
          step.ok === false && 'text-[var(--danger)]',
          step.ok === null && 'text-[var(--ink-muted)]',
        )}
      >
        {STEP_LABELS[step.kind] ?? step.kind}
      </span>
      <span className="min-w-0 break-words text-[var(--ink-muted)]">{step.detail}</span>
    </li>
  );
}

/** Horizontal outcome bar: applied / review / failed / skipped / remaining. */
export function RunProgressBar({
  totals,
  running,
}: {
  totals: { total: number; applied: number; needs_review: number; failed: number; skipped: number };
  running: boolean;
}) {
  const { total } = totals;
  if (!total) {
    return <div className="h-1.5 w-full rounded-full bg-[var(--surface-sunken)]" />;
  }

  const segments = [
    { key: 'applied', value: totals.applied, color: 'var(--ok)' },
    { key: 'needs_review', value: totals.needs_review, color: 'var(--warn)' },
    { key: 'failed', value: totals.failed, color: 'var(--danger)' },
    { key: 'skipped', value: totals.skipped, color: 'var(--ink-subtle)' },
  ].filter((s) => s.value > 0);

  const done = segments.reduce((sum, s) => sum + s.value, 0);
  const remaining = Math.max(0, total - done);

  return (
    <div className="relative flex h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-sunken)]">
      {segments.map((s) => (
        <span
          key={s.key}
          style={{ width: `${(s.value / total) * 100}%`, background: s.color }}
          className="h-full"
        />
      ))}
      {remaining > 0 && running && (
        <span
          style={{ width: `${(remaining / total) * 100}%` }}
          className="anim-sweep relative h-full overflow-hidden"
        />
      )}
    </div>
  );
}

'use client';

import clsx from 'clsx';
import { Check, ExternalLink, Image as ImageIcon, RotateCcw, Send, Trash2 } from 'lucide-react';
import type { Job } from '@/lib/types';
import { relativeTime } from '@/lib/platforms';
import {
  ApplyMethodBadge,
  ApplyStatusBadge,
  AtsBadge,
  PlatformBadge,
  ScoreBadge,
} from '@/components/ui/Badge';
import { IconButton } from '@/components/ui/Primitives';
import { api } from '@/lib/api';

export interface JobTableProps {
  jobs: Job[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  onVisit: (job: Job) => void;
  onApply: (job: Job) => void;
  onReset: (job: Job) => void;
  onDelete: (job: Job) => void;
  busy: boolean;
  /** Job ids currently being applied to, from the live run. */
  activeIds?: Set<string>;
}

export function JobTable({
  jobs,
  selected,
  onToggle,
  onToggleAll,
  onVisit,
  onApply,
  onReset,
  onDelete,
  busy,
  activeIds,
}: JobTableProps) {
  const allSelected = jobs.length > 0 && jobs.every((j) => selected.has(j.id));

  return (
    <div className="scroll-x">
      <table className="w-full min-w-[52rem] border-collapse text-left">
        <thead>
          <tr className="border-b border-[var(--line)]">
            <th className="w-9 px-3 py-2">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                aria-label="Select all jobs on this page"
              />
            </th>
            <Th className="min-w-[16rem]">Role</Th>
            <Th className="w-[9rem]">Apply route</Th>
            <Th className="w-[7rem]">Source</Th>
            <Th className="w-[4rem] text-center">Score</Th>
            <Th className="w-[8rem]">Outcome</Th>
            <Th className="w-[5.5rem]">Found</Th>
            <Th className="w-[6.5rem] text-right">Actions</Th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => {
            const visited = Boolean(job.visited_at);
            const active = activeIds?.has(job.id);
            const applied = job.status === 'applied' || job.apply_status === 'applied';
            const retryable =
              job.apply_status === 'failed' ||
              job.apply_status === 'needs_review' ||
              job.apply_status === 'skipped';

            return (
              <tr
                key={job.id}
                className={clsx(
                  'group relative border-b border-[var(--line)] transition-colors',
                  active
                    ? 'bg-[var(--accent-soft)]'
                    : selected.has(job.id)
                      ? 'bg-[var(--surface-hover)]'
                      : 'hover:bg-[var(--surface-hover)]',
                  visited && !active && 'opacity-65',
                )}
              >
                <td className="px-3 py-2.5 align-top">
                  <input
                    type="checkbox"
                    checked={selected.has(job.id)}
                    onChange={() => onToggle(job.id)}
                    aria-label={`Select ${job.title}`}
                  />
                </td>

                <td className="px-3 py-2.5 align-top">
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="truncate text-[13px] font-medium text-[var(--ink)]"
                        title={job.title}
                      >
                        {job.title}
                      </span>
                      {visited && <Check className="h-3 w-3 shrink-0 text-[var(--ok)]" />}
                    </div>
                    <span className="truncate text-[11px] text-[var(--ink-muted)]">
                      {job.company}
                      {job.location ? ` · ${job.location}` : ''}
                    </span>
                    {job.apply_error && !applied && (
                      <span
                        className="mt-0.5 line-clamp-2 max-w-[28rem] text-[11px] leading-snug text-[var(--warn)]"
                        title={job.apply_error}
                      >
                        {job.apply_error}
                      </span>
                    )}
                  </div>
                </td>

                <td className="px-3 py-2.5 align-top">
                  <div className="flex flex-col items-start gap-1">
                    <ApplyMethodBadge method={job.apply_method} auto={job.auto_appliable} />
                    <AtsBadge ats={job.ats_type} />
                  </div>
                </td>

                <td className="px-3 py-2.5 align-top">
                  <PlatformBadge platform={job.platform} />
                </td>

                <td className="px-3 py-2.5 text-center align-top">
                  <ScoreBadge score={job.relevance_score} />
                </td>

                <td className="px-3 py-2.5 align-top">
                  <ApplyStatusBadge status={active ? 'running' : job.apply_status} />
                </td>

                <td className="mono px-3 py-2.5 align-top text-[11px] text-[var(--ink-subtle)]">
                  {relativeTime(job.discovered_at)}
                </td>

                <td className="px-3 py-2.5 align-top">
                  <div className="flex items-center justify-end gap-0.5">
                    {job.apply_status && job.apply_status !== 'queued' && (
                      <a
                        href={api.screenshotUrl(job.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Screenshot from the last attempt"
                        className="inline-grid h-7 w-7 place-items-center rounded-md text-[var(--ink-subtle)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
                      >
                        <ImageIcon className="h-3.5 w-3.5" />
                      </a>
                    )}
                    {retryable && (
                      <IconButton
                        label="Clear outcome and requeue"
                        disabled={busy}
                        onClick={() => onReset(job)}
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                      </IconButton>
                    )}
                    <IconButton
                      label={applied ? 'Already applied' : 'Auto-apply to this job'}
                      disabled={busy || applied}
                      onClick={() => onApply(job)}
                      className={applied ? 'text-[var(--ok)]' : undefined}
                    >
                      <Send className="h-3.5 w-3.5" />
                    </IconButton>
                    <a
                      href={job.apply_url || job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={() => onVisit(job)}
                      title={job.apply_url ? 'Open the application form' : 'Open the posting'}
                      className="inline-grid h-7 w-7 place-items-center rounded-md text-[var(--ink-subtle)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--accent)]"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                    <IconButton
                      label="Delete job"
                      disabled={busy}
                      onClick={() => onDelete(job)}
                      className="hover:text-[var(--danger)]"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </IconButton>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      className={clsx(
        'px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-[var(--ink-subtle)]',
        className,
      )}
    >
      {children}
    </th>
  );
}

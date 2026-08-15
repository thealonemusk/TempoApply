'use client';

import clsx from 'clsx';
import { motion } from 'framer-motion';
import { Check, ExternalLink } from 'lucide-react';
import { Job } from '@/lib/types';
import { PlatformBadge, ScoreBadge, VisitedBadge } from '@/components/ui/Badge';

const STATUS_OPTIONS = [
  'discovered',
  'scored',
  'tailored',
  'applied',
  'interviewing',
  'rejected',
  'offer',
  'ignored',
];

interface JobRowProps {
  job: Job;
  index?: number;
  onStatusChange: (id: string, status: string) => void;
  onVisit: (id: string) => void;
}

export function JobRow({ job, index = 0, onStatusChange, onVisit }: JobRowProps) {
  const visited = Boolean(job.visited_at);
  const date = job.discovered_at
    ? new Date(job.discovered_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      })
    : '—';

  return (
    <motion.tr
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.02, duration: 0.2 }}
      className={clsx(
        'group border-b border-[var(--border)] transition-colors',
        visited
          ? 'bg-[var(--surface-2)]/60 opacity-75'
          : 'hover:bg-[var(--surface-2)]',
      )}
    >
      <td className="px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p
              className={clsx(
                'truncate text-sm font-medium',
                visited ? 'text-[var(--text-muted)]' : 'text-[var(--text-primary)]',
              )}
            >
              {job.title}
            </p>
            {visited && <VisitedBadge />}
          </div>
          <p className="truncate text-xs text-[var(--text-muted)]">
            {job.company}
            {job.location ? ` · ${job.location}` : ''}
          </p>
        </div>
      </td>
      <td className="px-4 py-3">
        <PlatformBadge platform={job.platform} />
      </td>
      <td className="px-4 py-3 text-center">
        <ScoreBadge score={job.relevance_score} />
      </td>
      <td className="px-4 py-3">
        <select
          value={job.status}
          onChange={(e) => onStatusChange(job.id, e.target.value)}
          className="cursor-pointer rounded-lg border-0 bg-transparent text-xs font-medium capitalize text-[var(--text-secondary)] outline-none focus:text-[var(--text-primary)]"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{date}</td>
      <td className="px-4 py-3 text-right">
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => !visited && onVisit(job.id)}
          className={clsx(
            'inline-flex rounded-lg p-2 transition-all group-hover:opacity-100',
            visited
              ? 'text-[var(--success)] opacity-100'
              : 'text-[var(--text-muted)] opacity-0 hover:bg-[var(--surface-3)] hover:text-[var(--accent)]',
          )}
          title={visited ? 'Already visited' : 'Open posting'}
        >
          {visited ? <Check className="h-4 w-4" /> : <ExternalLink className="h-4 w-4" />}
        </a>
      </td>
    </motion.tr>
  );
}

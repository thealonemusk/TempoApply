'use client';

import { useMemo, useState } from 'react';
import { Activity, Radio } from 'lucide-react';
import clsx from 'clsx';
import { useJobs, useRun } from '@/lib/hooks';
import { duration } from '@/lib/platforms';
import type { JobRunState } from '@/lib/runs';
import { PageBody, PageHeader, MetaList } from '@/components/PageHeader';
import { RunControls } from '@/components/RunControls';
import { RunJobRow, RunProgressBar } from '@/components/RunTimeline';
import { Card, EmptyState, Select } from '@/components/ui/Primitives';

const FILTERS: { value: JobRunState | 'all'; label: string }[] = [
  { value: 'all', label: 'All jobs' },
  { value: 'running', label: 'Applying' },
  { value: 'applied', label: 'Applied' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'failed', label: 'Failed' },
  { value: 'skipped', label: 'Skipped' },
  { value: 'queued', label: 'Queued' },
];

export default function RunsPage() {
  const { run: applyRun, connected } = useRun('apply');
  const { run: scanRun } = useRun('scan');
  const { jobs, reload } = useJobs(applyRun.totals.done);
  const [filter, setFilter] = useState<JobRunState | 'all'>('all');

  const eligibleCount = useMemo(
    () =>
      jobs.filter(
        (j) =>
          j.auto_appliable &&
          j.apply_status !== 'applied' &&
          j.status !== 'applied' &&
          !['failed', 'needs_review', 'skipped'].includes(j.apply_status),
      ).length,
    [jobs],
  );

  const visible = useMemo(() => {
    const rows = filter === 'all' ? applyRun.jobs : applyRun.jobs.filter((j) => j.state === filter);
    // Live work first, then finished, so the active job is always on screen.
    const rank: Record<JobRunState, number> = {
      running: 0,
      queued: 1,
      needs_review: 2,
      failed: 3,
      applied: 4,
      skipped: 5,
    };
    return [...rows].sort((a, b) => rank[a.state] - rank[b.state]);
  }, [applyRun.jobs, filter]);

  const t = applyRun.totals;
  const scanPlatforms = (scanRun.meta?.platforms ?? {}) as Record<
    string,
    { status?: string; found?: number; added?: number; error?: string }
  >;

  return (
    <>
      <PageHeader
        title="Runs"
        meta={
          <MetaList
            items={[
              applyRun.run_id ? `apply · ${applyRun.status}` : 'no apply run yet',
              applyRun.started_at
                ? `ran ${duration(applyRun.started_at, applyRun.finished_at)}`
                : null,
              !connected && 'backend offline',
            ]}
          />
        }
        actions={
          <RunControls
            applyRun={applyRun}
            scanRun={scanRun}
            eligibleCount={eligibleCount}
            onStarted={() => reload(true)}
            compact
          />
        }
      />

      <PageBody className="space-y-5">
        {/* Live apply run */}
        <Card padded={false}>
          <div className="border-b border-[var(--line)] p-5">
            <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em] text-[var(--ink)]">
                  Apply run
                  {applyRun.running && (
                    <span className="flex items-center gap-1 text-[11px] font-medium text-[var(--accent)]">
                      <Radio className="h-3 w-3 anim-pulse" />
                      live
                    </span>
                  )}
                </h2>
                <p className="mt-0.5 text-xs text-[var(--ink-muted)]">
                  {applyRun.message ||
                    (applyRun.run_id
                      ? `${t.done} of ${t.total} resolved`
                      : 'Start a run to see each job attempt and its steps here.')}
                </p>
              </div>
              {t.total > 0 && (
                <Select
                  value={filter}
                  onChange={(e) => setFilter(e.target.value as JobRunState | 'all')}
                  className="w-auto"
                >
                  {FILTERS.map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </Select>
              )}
            </div>

            <RunProgressBar totals={t} running={applyRun.running} />

            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
              <Stat label="Applied" value={t.applied} tone="ok" />
              <Stat label="Needs review" value={t.needs_review} tone="warn" />
              <Stat label="Failed" value={t.failed} tone="danger" />
              <Stat label="Skipped" value={t.skipped} />
              <Stat label="Queued" value={t.queued + t.running} tone="accent" />
            </div>

            {applyRun.error && (
              <p className="mt-3 rounded-[var(--radius)] bg-[var(--danger-soft)] px-3 py-2 text-[11px] leading-snug text-[var(--danger)]">
                {applyRun.message || applyRun.error}
              </p>
            )}

            {typeof applyRun.meta?.manual_only === 'number' &&
              (applyRun.meta.manual_only as number) > 0 && (
                <p className="mt-3 rounded-[var(--radius)] bg-[var(--warn-soft)] px-3 py-2 text-[11px] leading-snug text-[var(--warn)]">
                  {applyRun.meta.manual_only as number} job(s) in this run had no reachable
                  application form and were marked for manual apply. Only{' '}
                  {(applyRun.meta.auto_appliable as number) ?? 0} could be auto-submitted.
                </p>
              )}
          </div>

          {visible.length === 0 ? (
            <EmptyState
              icon={Activity}
              title={t.total ? 'Nothing matches this filter' : 'No apply attempts yet'}
              description={
                t.total
                  ? 'Change the filter to see the rest of the run.'
                  : 'Each job gets a step-by-step trace — which ATS it reached, what it filled, and where it stopped.'
              }
            />
          ) : (
            <div>
              {visible.map((job) => (
                <RunJobRow
                  key={job.job_id}
                  job={job}
                  defaultOpen={job.state === 'running' && visible.length <= 3}
                />
              ))}
            </div>
          )}
        </Card>

        {/* Scan run */}
        <Card padded={false}>
          <div className="border-b border-[var(--line)] p-5">
            <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em] text-[var(--ink)]">
              Scan run
              {scanRun.running && (
                <span className="flex items-center gap-1 text-[11px] font-medium text-[var(--accent)]">
                  <Radio className="h-3 w-3 anim-pulse" />
                  live
                </span>
              )}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--ink-muted)]">
              {scanRun.message ||
                (scanRun.run_id ? scanRun.status : 'Run a scan to discover new postings.')}
            </p>
          </div>

          {Object.keys(scanPlatforms).length === 0 ? (
            <EmptyState title="No scan yet" description="Platform-by-platform results appear here." />
          ) : (
            <div className="scroll-x">
              <table className="w-full min-w-[28rem] text-left">
                <thead>
                  <tr className="border-b border-[var(--line)] text-[11px] uppercase tracking-wide text-[var(--ink-subtle)]">
                    <th className="px-4 py-2 font-medium">Platform</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 text-right font-medium">Found</th>
                    <th className="px-4 py-2 text-right font-medium">New</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(scanPlatforms).map(([name, row]) => (
                    <tr key={name} className="border-b border-[var(--line)] last:border-b-0">
                      <td className="px-4 py-2 text-[13px] text-[var(--ink)]">{name}</td>
                      <td className="px-4 py-2">
                        <span
                          className={clsx(
                            'text-[11px] font-medium',
                            row.status === 'done' && 'text-[var(--ok)]',
                            row.status === 'running' && 'text-[var(--accent)] anim-pulse',
                            row.status === 'error' && 'text-[var(--danger)]',
                            (row.status === 'pending' || row.status === 'skipped') &&
                              'text-[var(--ink-subtle)]',
                          )}
                          title={row.error}
                        >
                          {row.status ?? 'pending'}
                        </span>
                      </td>
                      <td className="mono px-4 py-2 text-right text-[12px] text-[var(--ink-muted)]">
                        {row.found ?? 0}
                      </td>
                      <td className="mono px-4 py-2 text-right text-[12px] text-[var(--ink)]">
                        {row.added ?? 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </PageBody>
    </>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: 'ok' | 'warn' | 'danger' | 'accent';
}) {
  return (
    <div className="rounded-[var(--radius)] bg-[var(--surface-sunken)] px-3 py-2">
      <p
        className={clsx(
          'mono text-lg font-semibold leading-none',
          tone === 'ok' && 'text-[var(--ok)]',
          tone === 'warn' && 'text-[var(--warn)]',
          tone === 'danger' && 'text-[var(--danger)]',
          tone === 'accent' && 'text-[var(--accent)]',
          !tone && 'text-[var(--ink)]',
        )}
      >
        {value}
      </p>
      <p className="mt-1 text-[11px] text-[var(--ink-muted)]">{label}</p>
    </div>
  );
}

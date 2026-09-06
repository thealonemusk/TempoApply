'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import {
  ArrowRight,
  Hand,
  Radio,
  ShieldAlert,
  TriangleAlert,
  Zap,
} from 'lucide-react';
import clsx from 'clsx';
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '@/lib/api';
import { useFetch, useJobs, useRun } from '@/lib/hooks';
import { PLATFORM_COLORS, duration, platformLabel } from '@/lib/platforms';
import { PageBody, PageHeader, MetaList } from '@/components/PageHeader';
import { RunControls } from '@/components/RunControls';
import { RunProgressBar } from '@/components/RunTimeline';
import { Card, EmptyState, SectionHeader, Skeleton } from '@/components/ui/Primitives';
import { ApplyMethodBadge, ScoreBadge } from '@/components/ui/Badge';

export default function OverviewPage() {
  const { run: applyRun, connected } = useRun('apply');
  const { run: scanRun } = useRun('scan');
  const { jobs, loading, reload } = useJobs(applyRun.totals.done);
  const { data: profile } = useFetch(() => api.getProfile(), []);
  const { data: analytics } = useFetch(() => api.getAnalytics(), [applyRun.totals.done]);

  const stats = useMemo(() => {
    const auto = jobs.filter((j) => j.auto_appliable);
    const queued = auto.filter(
      (j) =>
        j.status !== 'applied' &&
        !['applied', 'failed', 'needs_review', 'skipped'].includes(j.apply_status),
    );
    return {
      total: jobs.length,
      auto: auto.length,
      manual: jobs.length - auto.length,
      queued: queued.length,
      applied: jobs.filter((j) => j.apply_status === 'applied' || j.status === 'applied').length,
      review: jobs.filter((j) => j.apply_status === 'needs_review').length,
      failed: jobs.filter((j) => j.apply_status === 'failed').length,
    };
  }, [jobs]);

  const topAuto = useMemo(
    () =>
      jobs
        .filter((j) => j.auto_appliable && j.apply_status !== 'applied')
        .sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0))
        .slice(0, 6),
    [jobs],
  );

  const platformData = useMemo(() => {
    if (!analytics) return [];
    return Object.entries(analytics.by_platform)
      .filter(([, v]) => v > 0)
      .map(([k, v]) => ({ name: platformLabel(k), value: v, fill: PLATFORM_COLORS[k] ?? '#8b8e9c' }))
      .sort((a, b) => b.value - a.value);
  }, [analytics]);

  const autoShare = stats.total ? Math.round((stats.auto / stats.total) * 100) : 0;
  const missing = profile?.missing ?? [];

  return (
    <>
      <PageHeader
        title="Overview"
        meta={
          <MetaList
            items={[
              connected ? 'API connected' : 'API offline',
              scanRun.running ? 'scanning…' : null,
              applyRun.running ? 'applying…' : null,
            ]}
          />
        }
        actions={
          <RunControls
            applyRun={applyRun}
            scanRun={scanRun}
            eligibleCount={stats.queued}
            onStarted={() => reload(true)}
            compact
          />
        }
      />

      <PageBody className="space-y-5">
        {/* Blockers first */}
        {!connected && (
          <Banner
            tone="danger"
            icon={ShieldAlert}
            title="Cannot reach the backend"
            body={`Start it with "python run.py" — the dashboard is reading from ${''}the API at localhost:8000.`}
          />
        )}
        {missing.length > 0 && (
          <Banner
            tone="warn"
            icon={TriangleAlert}
            title="Applicant profile is incomplete"
            body={`Auto-apply needs ${missing.join(', ')}. Fill it in before starting a run.`}
            href="/settings"
            hrefLabel="Complete profile"
          />
        )}

        {/* Live run */}
        {(applyRun.running || applyRun.run_id) && (
          <Card>
            <SectionHeader
              title="Latest apply run"
              description={
                applyRun.message ||
                `${applyRun.status} · ${duration(applyRun.started_at, applyRun.finished_at)}`
              }
              actions={
                <Link
                  href="/runs"
                  className="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--accent)] hover:underline"
                >
                  {applyRun.running && <Radio className="h-3 w-3 anim-pulse" />}
                  Open run
                  <ArrowRight className="h-3 w-3" />
                </Link>
              }
            />
            <RunProgressBar totals={applyRun.totals} running={applyRun.running} />
            <div className="mono mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[var(--ink-muted)]">
              <span className="text-[var(--ok)]">{applyRun.totals.applied} applied</span>
              <span className="text-[var(--warn)]">{applyRun.totals.needs_review} review</span>
              <span className="text-[var(--danger)]">{applyRun.totals.failed} failed</span>
              <span>{applyRun.totals.skipped} skipped</span>
              <span>
                {applyRun.totals.done}/{applyRun.totals.total} resolved
              </span>
            </div>
          </Card>
        )}

        {/* The headline number */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Auto-appliable"
            value={loading ? null : stats.auto}
            hint={stats.total ? `${autoShare}% of ${stats.total} jobs` : 'run a scan'}
            tone="accent"
            icon={Zap}
          />
          <StatCard
            label="Manual only"
            value={loading ? null : stats.manual}
            hint="no reachable form"
            icon={Hand}
          />
          <StatCard label="Applied" value={loading ? null : stats.applied} tone="ok" />
          <StatCard
            label="Needs review"
            value={loading ? null : stats.review + stats.failed}
            hint={`${stats.review} review · ${stats.failed} failed`}
            tone="warn"
          />
        </div>

        {/* The honest explanation of the ratio */}
        {!loading && stats.total > 0 && stats.manual > stats.auto && (
          <Banner
            tone="info"
            icon={Hand}
            title={`${stats.manual} of ${stats.total} jobs cannot be auto-applied`}
            body={
              'Aggregator postings hide the employer form behind a login, so there is nothing to fill. ' +
              'Auto-apply works on Greenhouse, Lever, Workday and Ashby links — which come from career-site scans.'
            }
            href="/jobs"
            hrefLabel="Review the queue"
          />
        )}

        <div className="grid gap-5 lg:grid-cols-5">
          {/* Ready to apply */}
          <Card padded={false} className="lg:col-span-3">
            <div className="p-5 pb-3">
              <SectionHeader
                title="Ready to auto-apply"
                description="Highest-scoring jobs with a reachable application form."
                actions={
                  <Link
                    href="/jobs"
                    className="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--accent)] hover:underline"
                  >
                    All jobs
                    <ArrowRight className="h-3 w-3" />
                  </Link>
                }
              />
            </div>
            {loading ? (
              <div className="space-y-2 px-5 pb-5">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-11 w-full" />
                ))}
              </div>
            ) : topAuto.length === 0 ? (
              <EmptyState
                icon={Zap}
                title="Nothing is auto-appliable yet"
                description="Career-site scans produce Greenhouse, Lever and Workday links, which are the ones auto-apply can submit."
              />
            ) : (
              <ul>
                {topAuto.map((job) => (
                  <li
                    key={job.id}
                    className="flex items-center gap-3 border-t border-[var(--line)] px-5 py-2.5"
                  >
                    <ScoreBadge score={job.relevance_score} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-medium text-[var(--ink)]">
                        {job.title}
                      </p>
                      <p className="truncate text-[11px] text-[var(--ink-muted)]">
                        {job.company}
                        {job.location ? ` · ${job.location}` : ''}
                      </p>
                    </div>
                    <ApplyMethodBadge method={job.apply_method} auto={job.auto_appliable} />
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Sources */}
          <Card className="lg:col-span-2">
            <SectionHeader title="Where jobs come from" description="Postings by source" />
            {platformData.length === 0 ? (
              <EmptyState title="No data yet" description="Run a scan to populate this." />
            ) : (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={platformData}
                    layout="vertical"
                    margin={{ top: 0, right: 12, left: 0, bottom: 0 }}
                  >
                    <XAxis type="number" hide />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={82}
                      tick={{ fontSize: 11, fill: 'var(--ink-muted)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--surface-raised)',
                        border: '1px solid var(--line)',
                        borderRadius: 'var(--radius)',
                        fontSize: 12,
                        color: 'var(--ink)',
                      }}
                      cursor={{ fill: 'var(--surface-hover)' }}
                    />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}>
                      {platformData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </div>
      </PageBody>
    </>
  );
}

function StatCard({
  label,
  value,
  hint,
  tone,
  icon: Icon,
}: {
  label: string;
  value: number | null;
  hint?: string;
  tone?: 'accent' | 'ok' | 'warn';
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--ink-subtle)]">
          {label}
        </p>
        {Icon && (
          <Icon
            className={clsx(
              'h-3.5 w-3.5',
              tone === 'accent' ? 'text-[var(--accent)]' : 'text-[var(--ink-subtle)]',
            )}
          />
        )}
      </div>
      {value === null ? (
        <Skeleton className="mt-2 h-8 w-14" />
      ) : (
        <p
          className={clsx(
            'mono mt-1.5 text-[28px] font-semibold leading-none tracking-tight',
            tone === 'accent' && 'text-[var(--accent)]',
            tone === 'ok' && 'text-[var(--ok)]',
            tone === 'warn' && 'text-[var(--warn)]',
            !tone && 'text-[var(--ink)]',
          )}
        >
          {value}
        </p>
      )}
      {hint && <p className="mt-1.5 text-[11px] text-[var(--ink-muted)]">{hint}</p>}
    </Card>
  );
}

function Banner({
  tone,
  icon: Icon,
  title,
  body,
  href,
  hrefLabel,
}: {
  tone: 'info' | 'warn' | 'danger';
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
  href?: string;
  hrefLabel?: string;
}) {
  const tones = {
    info: 'border-[var(--line)] bg-[var(--info-soft)] text-[var(--info)]',
    warn: 'border-[var(--warn)] bg-[var(--warn-soft)] text-[var(--warn)]',
    danger: 'border-[var(--danger)] bg-[var(--danger-soft)] text-[var(--danger)]',
  };

  return (
    <div
      className={clsx(
        'flex flex-wrap items-start gap-3 rounded-[var(--radius-lg)] border px-4 py-3',
        tones[tone],
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold">{title}</p>
        <p className="mt-0.5 text-[12px] leading-snug text-[var(--ink-muted)]">{body}</p>
      </div>
      {href && hrefLabel && (
        <Link
          href={href}
          className="inline-flex shrink-0 items-center gap-1 text-[12px] font-medium hover:underline"
        >
          {hrefLabel}
          <ArrowRight className="h-3 w-3" />
        </Link>
      )}
    </div>
  );
}

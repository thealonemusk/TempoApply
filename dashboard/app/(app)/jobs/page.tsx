'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, ListChecks, Plus, Search, Trash2, X, Zap } from 'lucide-react';
import clsx from 'clsx';
import { api, ApiError } from '@/lib/api';
import { useJobs, useLocalState, useRun } from '@/lib/hooks';
import { platformLabel } from '@/lib/platforms';
import type { Job } from '@/lib/types';
import { PageBody, PageHeader, MetaList } from '@/components/PageHeader';
import { JobTable } from '@/components/JobTable';
import { RunControls } from '@/components/RunControls';
import { useToast } from '@/components/ui/Toast';
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Modal,
  Select,
  Skeleton,
  Textarea,
} from '@/components/ui/Primitives';

const PER_PAGE = 25;
const FINISHED_STATUSES = ['applied', 'interviewing', 'rejected', 'offer', 'ignored'];

type RouteFilter = 'all' | 'auto' | 'manual';
type OutcomeFilter = 'all' | 'pending' | 'applied' | 'needs_review' | 'failed' | 'skipped';
type SortKey = 'score' | 'newest' | 'company';

export default function JobsPage() {
  const toast = useToast();
  const { run: applyRun } = useRun('apply');
  const { run: scanRun } = useRun('scan');
  const { jobs, loading, error, reload, patch } = useJobs(applyRun.totals.done);

  const [search, setSearch] = useState('');
  const [platform, setPlatform] = useState('');
  const [route, setRoute] = useLocalState<RouteFilter>('ta.jobs.route', 'all');
  const [outcome, setOutcome] = useState<OutcomeFilter>('all');
  const [sort, setSort] = useLocalState<SortKey>('ta.jobs.sort', 'score');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [confirm, setConfirm] = useState<null | {
    title: string;
    description: string;
    label: string;
    run: () => Promise<void>;
  }>(null);

  const [form, setForm] = useState({ title: '', company: '', url: '', jd_text: '', location: '' });

  const activeIds = useMemo(
    () => new Set(applyRun.jobs.filter((j) => j.state === 'running').map((j) => j.job_id)),
    [applyRun.jobs],
  );

  // ── filtering ─────────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return jobs.filter((j) => {
      if (platform && j.platform !== platform) return false;
      if (route === 'auto' && !j.auto_appliable) return false;
      if (route === 'manual' && j.auto_appliable) return false;
      if (outcome === 'pending' && j.apply_status) return false;
      if (outcome !== 'all' && outcome !== 'pending' && j.apply_status !== outcome) return false;
      if (!q) return true;
      return (
        j.title.toLowerCase().includes(q) ||
        j.company.toLowerCase().includes(q) ||
        j.location.toLowerCase().includes(q)
      );
    });
  }, [jobs, search, platform, route, outcome]);

  const sorted = useMemo(() => {
    const rows = [...filtered];
    rows.sort((a, b) => {
      // Unvisited before visited, then the chosen key.
      const av = a.visited_at ? 1 : 0;
      const bv = b.visited_at ? 1 : 0;
      if (av !== bv) return av - bv;
      if (sort === 'company') return a.company.localeCompare(b.company);
      if (sort === 'newest') {
        return (
          new Date(b.discovered_at ?? 0).getTime() - new Date(a.discovered_at ?? 0).getTime()
        );
      }
      // Auto-appliable first when sorting by score — that is the actionable set.
      if (a.auto_appliable !== b.auto_appliable) return a.auto_appliable ? -1 : 1;
      return (b.relevance_score || 0) - (a.relevance_score || 0);
    });
    return rows;
  }, [filtered, sort]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PER_PAGE));
  const pageRows = sorted.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  useEffect(() => setPage(1), [search, platform, route, outcome, sort]);
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const counts = useMemo(() => {
    const auto = jobs.filter((j) => j.auto_appliable).length;
    const queued = jobs.filter(
      (j) =>
        j.auto_appliable &&
        !FINISHED_STATUSES.includes(j.status) &&
        !['applied', 'failed', 'needs_review', 'skipped'].includes(j.apply_status),
    ).length;
    return { auto, manual: jobs.length - auto, queued };
  }, [jobs]);

  const platformOptions = useMemo(
    () => Array.from(new Set(jobs.map((j) => j.platform))).sort(),
    [jobs],
  );

  // ── actions ───────────────────────────────────────────────────────────────
  const guard = useCallback(
    async (label: string, fn: () => Promise<void>) => {
      setBusy(true);
      try {
        await fn();
      } catch (err) {
        toast.error(label, err instanceof ApiError ? err.message : 'Request failed');
      } finally {
        setBusy(false);
      }
    },
    [toast],
  );

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const toggleAll = () =>
    setSelected((prev) => {
      const allOn = pageRows.every((j) => prev.has(j.id));
      const next = new Set(prev);
      pageRows.forEach((j) => (allOn ? next.delete(j.id) : next.add(j.id)));
      return next;
    });

  const onVisit = (job: Job) => {
    if (job.visited_at) return;
    patch(job.id, { visited_at: new Date().toISOString() });
    api.markJobVisited(job.id).catch(() => {
      /* optimistic — a failed mark is not worth interrupting the user */
    });
  };

  const onApply = (job: Job) =>
    guard('Could not start apply', async () => {
      await api.applyJob(job.id);
      toast.success('Applying', `${job.title} @ ${job.company}`);
    });

  const onReset = (job: Job) =>
    guard('Could not requeue', async () => {
      await api.resetJobApply(job.id);
      patch(job.id, { apply_status: '', apply_error: '' });
      toast.success('Requeued', 'It will be picked up on the next run.');
    });

  const onDelete = (job: Job) =>
    setConfirm({
      title: 'Delete this job?',
      description: `${job.title} @ ${job.company} will be removed from the list.`,
      label: 'Delete',
      run: async () => {
        await api.deleteJob(job.id);
        toast.success('Job deleted');
        await reload(true);
      },
    });

  const applySelected = () => {
    const ids = Array.from(selected);
    const chosen = jobs.filter((j) => selected.has(j.id));
    const auto = chosen.filter((j) => j.auto_appliable).length;
    setConfirm({
      title: `Auto-apply to ${ids.length} selected job${ids.length === 1 ? '' : 's'}?`,
      description:
        auto === ids.length
          ? 'Your saved profile will be used to fill and submit each form.'
          : `${auto} of ${ids.length} have a reachable form. The rest will be marked for manual apply.`,
      label: 'Start run',
      run: async () => {
        await api.startApply({ job_ids: ids });
        setSelected(new Set());
        toast.success('Apply run started', 'Watch progress on the Runs page.');
      },
    });
  };

  const addManual = () =>
    guard('Could not add the job', async () => {
      await api.addManualJob(form);
      setAddOpen(false);
      setForm({ title: '', company: '', url: '', jd_text: '', location: '' });
      toast.success('Job added');
      await reload(true);
    });

  return (
    <>
      <PageHeader
        title="Jobs"
        meta={
          <MetaList
            items={[
              `${jobs.length} in queue`,
              `${counts.auto} auto-appliable`,
              counts.manual > 0 && `${counts.manual} manual only`,
              sorted.length !== jobs.length && `${sorted.length} shown`,
            ]}
          />
        }
        actions={
          <>
            <Button variant="ghost" size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="h-3.5 w-3.5" />
              Add
            </Button>
            <RunControls
              applyRun={applyRun}
              scanRun={scanRun}
              eligibleCount={counts.queued}
              onStarted={() => reload(true)}
              compact
            />
          </>
        }
      />

      <PageBody className="space-y-4">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[13rem] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--ink-subtle)]" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search role, company, location"
              className="pl-8"
            />
          </div>
          <Select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="w-auto">
            <option value="score">Best match</option>
            <option value="newest">Newest</option>
            <option value="company">Company</option>
          </Select>
          <Select
            value={outcome}
            onChange={(e) => setOutcome(e.target.value as OutcomeFilter)}
            className="w-auto"
          >
            <option value="all">Any outcome</option>
            <option value="pending">Not attempted</option>
            <option value="applied">Applied</option>
            <option value="needs_review">Needs review</option>
            <option value="failed">Failed</option>
            <option value="skipped">Skipped</option>
          </Select>
          <Select value={platform} onChange={(e) => setPlatform(e.target.value)} className="w-auto">
            <option value="">All sources</option>
            {platformOptions.map((p) => (
              <option key={p} value={p}>
                {platformLabel(p)}
              </option>
            ))}
          </Select>
        </div>

        {/* Apply-route segmented control — the most consequential filter */}
        <div className="inline-flex rounded-[var(--radius)] border border-[var(--line)] bg-[var(--surface)] p-0.5">
          {(
            [
              { key: 'all', label: `All ${jobs.length}` },
              { key: 'auto', label: `Auto-appliable ${counts.auto}` },
              { key: 'manual', label: `Manual only ${counts.manual}` },
            ] as { key: RouteFilter; label: string }[]
          ).map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setRoute(key)}
              className={clsx(
                'rounded-[calc(var(--radius)-2px)] px-2.5 py-1 text-[12px] font-medium transition-colors',
                route === key
                  ? 'bg-[var(--accent)] text-[var(--on-accent)]'
                  : 'text-[var(--ink-muted)] hover:text-[var(--ink)]',
              )}
            >
              {key === 'auto' && <Zap className="mr-1 inline h-2.5 w-2.5" />}
              {label}
            </button>
          ))}
        </div>

        {/* Bulk bar */}
        {selected.size > 0 && (
          <div className="anim-fade-up flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border border-[var(--accent)] bg-[var(--accent-soft)] px-3 py-2">
            <span className="text-[13px] font-medium text-[var(--accent)]">
              {selected.size} selected
            </span>
            <div className="flex items-center gap-2">
              <Button size="xs" variant="secondary" onClick={() => setSelected(new Set())}>
                Clear
              </Button>
              <Button
                size="xs"
                disabled={busy || applyRun.running || scanRun.running}
                onClick={applySelected}
              >
                <Zap className="h-3 w-3" />
                Auto-apply selected
              </Button>
            </div>
          </div>
        )}

        {/* Table */}
        <Card padded={false} className="overflow-hidden">
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={() => reload()} />
          ) : pageRows.length === 0 ? (
            <EmptyState
              icon={ListChecks}
              title={jobs.length === 0 ? 'No jobs yet' : 'Nothing matches these filters'}
              description={
                jobs.length === 0
                  ? 'Run a scan to discover postings, or add one manually.'
                  : 'Try clearing the search or switching the apply-route filter.'
              }
              action={
                jobs.length > 0 ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setSearch('');
                      setPlatform('');
                      setRoute('all');
                      setOutcome('all');
                    }}
                  >
                    Clear filters
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <>
              <JobTable
                jobs={pageRows}
                selected={selected}
                onToggle={toggle}
                onToggleAll={toggleAll}
                onVisit={onVisit}
                onApply={onApply}
                onReset={onReset}
                onDelete={onDelete}
                busy={busy || applyRun.running}
                activeIds={activeIds}
              />
              <div className="flex items-center justify-between gap-3 border-t border-[var(--line)] px-3 py-2.5">
                <span className="mono text-[11px] text-[var(--ink-subtle)]">
                  {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, sorted.length)} of{' '}
                  {sorted.length}
                </span>
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="secondary"
                    size="xs"
                    disabled={page === 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </Button>
                  <span className="mono px-1 text-[11px] text-[var(--ink-muted)]">
                    {page}/{totalPages}
                  </span>
                  <Button
                    variant="secondary"
                    size="xs"
                    disabled={page === totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </Card>

        <div className="flex flex-wrap justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={busy}
            onClick={() =>
              setConfirm({
                title: 'Clear discovered jobs?',
                description:
                  'Removes every job still in discovered or scored status. Applied jobs are kept.',
                label: 'Clear',
                run: async () => {
                  const { deleted_count } = await api.clearDiscoveredJobs();
                  toast.success(`Cleared ${deleted_count} job(s)`);
                  setSelected(new Set());
                  await reload(true);
                },
              })
            }
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear discovered
          </Button>
        </div>
      </PageBody>

      {/* Add job */}
      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add a job"
        description="Paste a posting you found yourself. A direct ATS link makes it auto-appliable."
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              loading={busy}
              disabled={!form.title || !form.company || !form.url}
              onClick={addManual}
            >
              Add job
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Role">
              <Input
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Software Engineer"
              />
            </Field>
            <Field label="Company">
              <Input
                value={form.company}
                onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))}
                placeholder="Acme"
              />
            </Field>
          </div>
          <Field label="Application URL" hint="A Greenhouse, Lever, Workday or Ashby link works best.">
            <Input
              value={form.url}
              onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
              placeholder="https://boards.greenhouse.io/acme/jobs/123"
            />
          </Field>
          <Field label="Location">
            <Input
              value={form.location}
              onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
              placeholder="Bengaluru, India"
            />
          </Field>
          <Field label="Job description" hint="Used for filtering and cover-letter context.">
            <Textarea
              rows={5}
              value={form.jd_text}
              onChange={(e) => setForm((f) => ({ ...f, jd_text: e.target.value }))}
            />
          </Field>
        </div>
      </Modal>

      <ConfirmDialog
        open={confirm !== null}
        title={confirm?.title ?? ''}
        description={confirm?.description}
        confirmLabel={confirm?.label}
        destructive={confirm?.label === 'Delete' || confirm?.label === 'Clear'}
        busy={busy}
        onCancel={() => setConfirm(null)}
        onConfirm={() => {
          const action = confirm;
          setConfirm(null);
          if (action) void guard(action.title, action.run);
        }}
      />
    </>
  );
}

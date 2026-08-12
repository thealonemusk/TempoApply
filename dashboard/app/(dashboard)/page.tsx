'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, X, ChevronLeft, ChevronRight } from 'lucide-react';
import clsx from 'clsx';
import { api } from '@/lib/api';
import { DEFAULT_SCAN_PLATFORMS, PLATFORM_LABELS, platformLabel } from '@/lib/platforms';
import type { Job } from '@/lib/types';
import { ScanBar } from '@/components/ScanBar';
import { JobRow } from '@/components/JobRow';
import { Button } from '@/components/ui/Button';
import { Input, Label, Textarea } from '@/components/ui/Input';

const JOBS_PER_PAGE = 20;

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [search, setSearch] = useState('');
  const [filterPlatform, setFilterPlatform] = useState('');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [sortBy, setSortBy] = useState<'score' | 'date'>('score');
  const [currentPage, setCurrentPage] = useState(1);
  const [addOpen, setAddOpen] = useState(false);
  const [manualForm, setManualForm] = useState({
    title: '',
    company: '',
    url: '',
    jd_text: '',
    location: '',
  });

  const loadJobs = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      setJobs(await api.getJobs());
    } catch {
      if (!quiet) setJobs([]);
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    api.getScanStatus().then((s) => setScanning(!!s.running)).catch(() => {});
  }, [loadJobs]);

  useEffect(() => {
    if (!scanning) return;
    const id = setInterval(async () => {
      try {
        const status = await api.getScanStatus();
        await loadJobs(true);
        if (!status.running) setScanning(false);
      } catch {}
    }, 3000);
    return () => clearInterval(id);
  }, [scanning, loadJobs]);

  const handleScan = async () => {
    if (scanning) return;
    try {
      setScanning(true);
      setCurrentPage(1);
      await api.startScan();
    } catch {
      setScanning(false);
    }
  };

  const handleStatusChange = async (id: string, status: string) => {
    await api.updateJobStatus(id, status);
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, status: status as Job['status'] } : j)));
  };

  const handleAddManual = async () => {
    await api.addManualJob(manualForm);
    setAddOpen(false);
    setManualForm({ title: '', company: '', url: '', jd_text: '', location: '' });
    loadJobs();
  };

  const handleClearJobs = async () => {
    if (!confirm('Clear all discovered jobs that are not applied?')) return;
    await api.clearDiscoveredJobs();
    setCurrentPage(1);
    loadJobs();
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return jobs.filter((j) => {
      if (filterPlatform && j.platform !== filterPlatform) return false;
      if (!q) return true;
      return (
        j.title.toLowerCase().includes(q) ||
        j.company.toLowerCase().includes(q) ||
        j.location.toLowerCase().includes(q)
      );
    });
  }, [jobs, search, filterPlatform]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      if (sortBy === 'score') {
        const diff = (b.relevance_score || 0) - (a.relevance_score || 0);
        if (diff !== 0) return sortOrder === 'desc' ? diff : -diff;
      }
      const tA = a.discovered_at ? new Date(a.discovered_at).getTime() : 0;
      const tB = b.discovered_at ? new Date(b.discovered_at).getTime() : 0;
      return sortOrder === 'desc' ? tB - tA : tA - tB;
    });
  }, [filtered, sortOrder, sortBy]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / JOBS_PER_PAGE));
  const pageJobs = sorted.slice((currentPage - 1) * JOBS_PER_PAGE, currentPage * JOBS_PER_PAGE);

  useEffect(() => setCurrentPage(1), [search, filterPlatform, sortOrder, sortBy]);

  const platformChips = useMemo(() => {
    const fromJobs = jobs.map((j) => j.platform);
    const keys = Array.from(new Set([...DEFAULT_SCAN_PLATFORMS, ...fromJobs]));
    return keys.filter((k) => PLATFORM_LABELS[k] || k);
  }, [jobs]);

  const pendingStatuses: Job['status'][] = ['discovered', 'scored'];
  const pendingCount = jobs.filter((j) => pendingStatuses.includes(j.status)).length;

  return (
    <>
      <header className="glass sticky top-0 z-20 border-b border-[var(--border)] px-8 py-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">Jobs</h1>
            <p className="mt-0.5 text-sm text-[var(--text-muted)]">
              {jobs.length} total
              {pendingCount > 0 && ` · ${pendingCount} pending`}
              {scanning && ' · scanning…'}
            </p>
          </div>
          <ScanBar
            scanning={scanning}
            onScan={handleScan}
            onAdd={() => setAddOpen(true)}
            onClear={handleClearJobs}
          />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-6xl space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-[220px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search title or company"
                className="pl-10"
              />
            </div>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'score' | 'date')}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5 text-sm text-[var(--text-secondary)] outline-none"
            >
              <option value="score">Best match</option>
              <option value="date">Date</option>
            </select>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as 'desc' | 'asc')}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5 text-sm text-[var(--text-secondary)] outline-none"
            >
              <option value="desc">{sortBy === 'score' ? 'Highest score' : 'Newest'}</option>
              <option value="asc">{sortBy === 'score' ? 'Lowest score' : 'Oldest'}</option>
            </select>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setFilterPlatform('')}
              className={clsx(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                !filterPlatform
                  ? 'bg-[var(--text-primary)] text-[var(--bg)]'
                  : 'bg-[var(--surface-2)] text-[var(--text-secondary)] hover:bg-[var(--surface-3)]',
              )}
            >
              All
            </button>
            {platformChips.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setFilterPlatform(p)}
                className={clsx(
                  'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                  filterPlatform === p
                    ? 'bg-[var(--text-primary)] text-[var(--bg)]'
                    : 'bg-[var(--surface-2)] text-[var(--text-secondary)] hover:bg-[var(--surface-3)]',
                )}
              >
                {platformLabel(p)}
              </button>
            ))}
          </div>

          <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-sm">
            {loading ? (
              <div className="p-16 text-center text-sm text-[var(--text-muted)]">Loading…</div>
            ) : sorted.length === 0 ? (
              <div className="p-16 text-center text-sm text-[var(--text-muted)]">
                No jobs yet. Run a scan to discover roles.
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-[var(--border)] text-xs font-medium text-[var(--text-muted)]">
                        <th className="px-4 py-3">Role</th>
                        <th className="px-4 py-3">Source</th>
                        <th className="px-4 py-3 text-center">Score</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Found</th>
                        <th className="px-4 py-3" />
                      </tr>
                    </thead>
                    <tbody>
                      {pageJobs.map((job, i) => (
                        <JobRow key={job.id} job={job} index={i} onStatusChange={handleStatusChange} />
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between border-t border-[var(--border)] px-4 py-3 text-sm text-[var(--text-muted)]">
                  <span>
                    {(currentPage - 1) * JOBS_PER_PAGE + 1}–{Math.min(currentPage * JOBS_PER_PAGE, sorted.length)} of{' '}
                    {sorted.length}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={currentPage === 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={currentPage === totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <AnimatePresence>
        {addOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 backdrop-blur-sm sm:items-center"
            onClick={() => setAddOpen(false)}
          >
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 24 }}
              transition={{ type: 'spring', damping: 28, stiffness: 320 }}
              className="w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="mb-5 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">Add job</h2>
                <button
                  type="button"
                  onClick={() => setAddOpen(false)}
                  className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--surface-2)]"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-4">
                {(['title', 'company', 'url', 'location'] as const).map((field) => (
                  <div key={field}>
                    <Label>{field.charAt(0).toUpperCase() + field.slice(1)}</Label>
                    <Input
                      value={manualForm[field]}
                      onChange={(e) => setManualForm((p) => ({ ...p, [field]: e.target.value }))}
                    />
                  </div>
                ))}
                <div>
                  <Label>Description</Label>
                  <Textarea
                    rows={4}
                    value={manualForm.jd_text}
                    onChange={(e) => setManualForm((p) => ({ ...p, jd_text: e.target.value }))}
                  />
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setAddOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddManual}>Save</Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

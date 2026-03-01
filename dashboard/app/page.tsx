'use client';

import Sidebar from './components/Sidebar';
import { JobCard, Job, JobStatus } from './components/JobCard';
import { useEffect, useState } from 'react';
import { RefreshCw, Plus, X, Briefcase, CheckSquare, TrendingUp } from 'lucide-react';
import clsx from 'clsx';

const COLUMNS: { id: JobStatus; label: string; emoji: string }[] = [
  { id: 'discovered', label: 'Discovered', emoji: '🔍' },
  { id: 'scored', label: 'Scored', emoji: '🧠' },
  { id: 'tailored', label: 'Tailored', emoji: '✂️' },
  { id: 'applied', label: 'Applied', emoji: '📤' },
  { id: 'interviewing', label: 'Interviewing', emoji: '💬' },
  { id: 'rejected', label: 'Rejected', emoji: '❌' },
  { id: 'offer', label: 'Offer!', emoji: '🎉' },
];

const COL_COLORS: Record<string, string> = {
  discovered: '#6366f1', scored: '#8b5cf6', tailored: '#3b82f6',
  applied: '#0ea5e9', interviewing: '#10b981', rejected: '#ef4444', offer: '#f59e0b',
};

const API = 'http://localhost:8000';

export default function PipelinePage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<string | null>(null);
  const [filterPlatform, setFilterPlatform] = useState('');
  const [addJobOpen, setAddJobOpen] = useState(false);
  const [manualForm, setManualForm] = useState({ title: '', company: '', url: '', jd_text: '', location: '' });

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/jobs`);
      const data = await res.json();
      setJobs(data);
    } catch {
      setJobs([]);
    }
    setLoading(false);
  };

  useEffect(() => { fetchJobs(); }, []);

  const handleStatusChange = async (id: string, status: string) => {
    await fetch(`${API}/api/jobs/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    setJobs(prev => prev.map(j => j.id === id ? { ...j, status: status as JobStatus } : j));
  };

  const handleGenerate = async (id: string) => {
    setGenerating(id);
    await fetch(`${API}/api/applications/${id}/generate`, { method: 'POST' });
    setTimeout(() => { setGenerating(null); fetchJobs(); }, 3000);
  };

  const handleAddManual = async () => {
    await fetch(`${API}/api/jobs/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(manualForm),
    });
    setAddJobOpen(false);
    setManualForm({ title: '', company: '', url: '', jd_text: '', location: '' });
    fetchJobs();
  };

  const filtered = filterPlatform ? jobs.filter(j => j.platform === filterPlatform) : jobs;
  const jobsByStatus = (status: JobStatus) => filtered.filter(j => j.status === status);

  const applied = jobs.filter(j => j.status === 'applied').length;
  const interviewing = jobs.filter(j => j.status === 'interviewing').length;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-x-auto flex flex-col">

        {/* Top bar */}
        <header className="glass border-b border-border px-6 py-4 sticky top-0 z-20 flex items-center justify-between gap-4 flex-shrink-0">
          <div>
            <h1 className="font-display font-bold text-2xl text-txt-primary tracking-tight">
              Pipeline
            </h1>
            <p className="text-xs text-txt-muted mt-0.5">
              {jobs.length} tracked · {applied} applied · {interviewing} interviewing
            </p>
          </div>

          {/* Stats pills */}
          <div className="hidden md:flex items-center gap-3">
            <div className="flex items-center gap-2 glass px-3 py-1.5 rounded-full border border-border">
              <Briefcase className="w-3.5 h-3.5 text-accent-light" />
              <span className="text-xs font-semibold text-txt-secondary">{jobs.length} Total</span>
            </div>
            <div className="flex items-center gap-2 glass px-3 py-1.5 rounded-full border border-border">
              <CheckSquare className="w-3.5 h-3.5 text-emerald" />
              <span className="text-xs font-semibold text-txt-secondary">{applied} Applied</span>
            </div>
            <div className="flex items-center gap-2 glass px-3 py-1.5 rounded-full border border-border">
              <TrendingUp className="w-3.5 h-3.5 text-gold" />
              <span className="text-xs font-semibold text-txt-secondary">{interviewing} Interviews</span>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <select
              value={filterPlatform}
              onChange={e => setFilterPlatform(e.target.value)}
              className="input-field text-xs rounded-lg px-2.5 py-1.5 text-txt-secondary"
            >
              <option value="">All Platforms</option>
              <option value="linkedin">LinkedIn</option>
              <option value="indeed">Indeed</option>
              <option value="naukri">Naukri</option>
              <option value="instahyre">InstaHyre</option>
              <option value="manual">Manual</option>
            </select>
            <button
              onClick={() => setAddJobOpen(true)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-border text-txt-secondary hover:border-accent/50 hover:text-accent-light transition-all"
            >
              <Plus className="w-3.5 h-3.5" /> Add Job
            </button>
            <button
              onClick={fetchJobs}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-accent/10 border border-accent/30 text-accent-light hover:bg-accent/20 transition-all"
            >
              <RefreshCw className={clsx('w-3.5 h-3.5', loading && 'animate-spin')} />
              Refresh
            </button>
          </div>
        </header>

        {/* Kanban */}
        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center space-y-3">
              <div className="w-12 h-12 rounded-full border-2 border-accent border-t-transparent animate-spin mx-auto" />
              <p className="text-txt-secondary text-sm">Loading pipeline…</p>
            </div>
          </div>
        ) : (
          <div className="flex gap-4 p-6 min-w-max flex-1">
            {COLUMNS.map((col) => {
              const colJobs = jobsByStatus(col.id);
              const color = COL_COLORS[col.id];
              return (
                <div key={col.id} className="w-72 flex-shrink-0 flex flex-col">
                  {/* Column header */}
                  <div className="mb-3 px-1">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm">{col.emoji}</span>
                        <h2 className="text-sm font-display font-semibold text-txt-primary">
                          {col.label}
                        </h2>
                      </div>
                      <span
                        className="text-xs font-mono font-bold px-2 py-0.5 rounded-full"
                        style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}
                      >
                        {colJobs.length}
                      </span>
                    </div>
                    <div className="h-0.5 rounded-full" style={{ background: `linear-gradient(90deg, ${color}80, transparent)` }} />
                  </div>

                  {/* Cards */}
                  <div className="space-y-2.5 overflow-y-auto max-h-[calc(100vh-160px)] pr-0.5">
                    {colJobs.length === 0 ? (
                      <div className="border border-dashed border-border rounded-xl p-5 text-center">
                        <p className="text-xs text-txt-muted">No jobs here yet</p>
                      </div>
                    ) : (
                      colJobs.map(job => (
                        <JobCard
                          key={job.id}
                          job={job}
                          onStatusChange={handleStatusChange}
                          onGenerate={handleGenerate}
                          generating={generating === job.id}
                        />
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Add Manual Job Modal */}
        {addJobOpen && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
            <div className="glass-bright rounded-2xl w-full max-w-lg shadow-card-lg border border-border-bright animate-fade-in-up">
              <div className="p-5 border-b border-border flex items-center justify-between">
                <div>
                  <h2 className="font-display font-bold text-lg text-txt-primary">Add Job Manually</h2>
                  <p className="text-xs text-txt-muted mt-0.5">Paste any job description for AI analysis</p>
                </div>
                <button onClick={() => setAddJobOpen(false)} className="p-1.5 rounded-lg hover:bg-white/5 text-txt-muted hover:text-txt-primary transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-5 space-y-3">
                {(['title', 'company', 'url', 'location'] as const).map(field => (
                  <div key={field}>
                    <label className="text-xs font-semibold uppercase tracking-wider text-txt-muted block mb-1.5">
                      {field}
                    </label>
                    <input
                      value={manualForm[field] as string}
                      onChange={e => setManualForm(prev => ({ ...prev, [field]: e.target.value }))}
                      placeholder={field === 'url' ? 'https://…' : `Enter ${field}`}
                      className="input-field w-full rounded-lg px-3 py-2 text-sm"
                    />
                  </div>
                ))}
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider text-txt-muted block mb-1.5">
                    Job Description
                  </label>
                  <textarea
                    value={manualForm.jd_text}
                    onChange={e => setManualForm(prev => ({ ...prev, jd_text: e.target.value }))}
                    rows={5}
                    placeholder="Paste the full job description here…"
                    className="input-field w-full rounded-lg px-3 py-2 text-sm resize-none"
                  />
                </div>
              </div>
              <div className="p-5 border-t border-border flex gap-3 justify-end">
                <button
                  onClick={() => setAddJobOpen(false)}
                  className="px-4 py-2 text-sm border border-border text-txt-secondary hover:border-border-bright hover:text-txt-primary rounded-lg transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddManual}
                  className="px-4 py-2 text-sm bg-accent hover:bg-accent-2 text-white rounded-lg font-semibold transition-all shadow-glow-sm"
                >
                  Analyze & Add
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

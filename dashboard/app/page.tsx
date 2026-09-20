'use client';

import Sidebar from './components/Sidebar';
import { JobCard, Job, JobStatus } from './components/JobCard';
import { useEffect, useState } from 'react';
import { Newspaper, RefreshCw, Plus, Filter } from 'lucide-react';
import clsx from 'clsx';

const COLUMNS: { id: JobStatus; label: string; desc: string }[] = [
  { id: 'discovered', label: 'Discovered', desc: 'New jobs found' },
  { id: 'scored', label: 'Scored', desc: 'AI analyzed' },
  { id: 'tailored', label: 'Tailored', desc: 'Resume ready' },
  { id: 'applied', label: 'Applied', desc: 'Submitted' },
  { id: 'interviewing', label: 'Interviewing', desc: 'In process' },
  { id: 'rejected', label: 'Rejected', desc: 'No match' },
  { id: 'offer', label: 'Offer!', desc: '🎉 Congrats' },
];

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
    setTimeout(() => {
      setGenerating(null);
      fetchJobs();
    }, 3000);
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

  const today = new Date().toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-x-auto">
        {/* Masthead */}
        <header className="bg-newsprint border-b-4 border-double border-ink px-6 py-4 sticky top-0 z-10">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-sans uppercase tracking-[0.3em] text-ink-muted">{today}</p>
              <h1 className="font-serif text-3xl font-black text-ink leading-tight">
                Application Pipeline
              </h1>
              <div className="w-full h-px bg-gradient-to-r from-ink via-accent-gold to-ink mt-1" />
              <p className="text-xs font-sans text-ink-muted mt-1">
                {jobs.length} jobs tracked · {jobs.filter(j => j.status === 'applied').length} applied
              </p>
            </div>
            <div className="flex items-center gap-3">
              {/* Platform filter */}
              <select
                value={filterPlatform}
                onChange={e => setFilterPlatform(e.target.value)}
                className="text-xs border border-newsprint-dark rounded bg-newsprint text-ink py-1.5 px-2 focus:outline-none focus:border-accent-gold"
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
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border-2 border-ink text-ink hover:bg-ink hover:text-newsprint transition-colors font-semibold"
              >
                <Plus className="w-3.5 h-3.5" /> Add Job
              </button>
              <button
                onClick={fetchJobs}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border-2 border-accent-gold text-accent-gold hover:bg-accent-gold hover:text-ink transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Refresh
              </button>
            </div>
          </div>
        </header>

        {/* Kanban Board */}
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <Newspaper className="w-12 h-12 text-ink-muted mx-auto mb-3 animate-pulse" />
              <p className="font-serif text-xl font-bold">Loading the press…</p>
            </div>
          </div>
        ) : (
          <div className="flex gap-0 p-6 min-w-max">
            {COLUMNS.map((col, idx) => {
              const colJobs = jobsByStatus(col.id);
              const isLast = idx === COLUMNS.length - 1;
              return (
                <div
                  key={col.id}
                  className={clsx(
                    'w-72 flex-shrink-0 flex flex-col',
                    !isLast && 'border-r border-newsprint-dark mr-5 pr-5'
                  )}
                >
                  {/* Column header */}
                  <div className="mb-4">
                    <div className="flex items-center justify-between">
                      <h2 className="font-serif font-bold text-sm text-ink uppercase tracking-wide">
                        {col.label}
                      </h2>
                      <span className="font-mono text-xs bg-ink text-newsprint px-1.5 py-0.5 rounded">
                        {colJobs.length}
                      </span>
                    </div>
                    <p className="text-xs text-ink-muted font-sans">{col.desc}</p>
                    <div className="mt-2 h-0.5 bg-gradient-to-r from-ink/40 to-transparent" />
                  </div>

                  {/* Cards */}
                  <div className="space-y-3 overflow-y-auto max-h-[calc(100vh-200px)] pr-1">
                    {colJobs.length === 0 ? (
                      <div className="border border-dashed border-newsprint-dark rounded p-4 text-center">
                        <p className="text-xs text-ink-muted italic">No stories yet</p>
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
          <div className="fixed inset-0 bg-ink/60 flex items-center justify-center z-50 p-4">
            <div className="bg-newsprint rounded-lg border-2 border-ink w-full max-w-lg shadow-newspaper-lg animate-fade-in-up">
              <div className="p-5 border-b-2 border-ink">
                <h2 className="font-serif text-2xl font-bold">Add Job Manually</h2>
                <p className="text-sm text-ink-muted">Paste any job description for AI analysis</p>
              </div>
              <div className="p-5 space-y-3">
                {(['title', 'company', 'url', 'location'] as const).map(field => (
                  <div key={field}>
                    <label className="text-xs font-semibold uppercase tracking-wide text-ink-muted block mb-1">
                      {field}
                    </label>
                    <input
                      value={manualForm[field] as string}
                      onChange={e => setManualForm(prev => ({ ...prev, [field]: e.target.value }))}
                      placeholder={field === 'url' ? 'https://…' : `Enter ${field}`}
                      className="w-full border border-newsprint-dark rounded px-3 py-2 text-sm bg-newsprint focus:outline-none focus:border-accent-gold"
                    />
                  </div>
                ))}
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-ink-muted block mb-1">
                    Job Description
                  </label>
                  <textarea
                    value={manualForm.jd_text}
                    onChange={e => setManualForm(prev => ({ ...prev, jd_text: e.target.value }))}
                    rows={6}
                    placeholder="Paste the full job description here…"
                    className="w-full border border-newsprint-dark rounded px-3 py-2 text-sm bg-newsprint focus:outline-none focus:border-accent-gold resize-none"
                  />
                </div>
              </div>
              <div className="p-5 border-t border-newsprint-dark flex gap-3 justify-end">
                <button
                  onClick={() => setAddJobOpen(false)}
                  className="px-4 py-2 text-sm border border-newsprint-dark rounded text-ink-muted hover:border-ink hover:text-ink transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddManual}
                  className="px-4 py-2 text-sm bg-ink text-newsprint rounded font-semibold hover:bg-ink-light transition-colors"
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

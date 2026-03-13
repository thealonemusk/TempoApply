'use client';

import Sidebar from './components/Sidebar';
import { Job, JobStatus } from './components/JobCard';
import { JobTableRow } from './components/JobTableRow';
import { useEffect, useState } from 'react';
import { RefreshCw, Plus, X, Briefcase, CheckSquare, TrendingUp, Search, Brain, Scissors, Send, MessageSquare, XCircle, Award } from 'lucide-react';
import clsx from 'clsx';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

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

  const applied = jobs.filter(j => j.status === 'applied').length;
  const interviewing = jobs.filter(j => j.status === 'interviewing').length;
  const offers = jobs.filter(j => j.status === 'offer').length;

  // Mock data for the chart based on jobs. It shows activity over the last 6 days.
  const chartData = [
    { name: 'Mon', jobs: Math.floor(jobs.length * 0.1) },
    { name: 'Tue', jobs: Math.floor(jobs.length * 0.2) },
    { name: 'Wed', jobs: Math.floor(jobs.length * 0.15) },
    { name: 'Thu', jobs: Math.floor(jobs.length * 0.3) },
    { name: 'Fri', jobs: Math.floor(jobs.length * 0.05) },
    { name: 'Sat', jobs: Math.floor(jobs.length * 0.2) },
    { name: 'Sun', jobs: jobs.length },
  ];

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-x-auto overflow-y-auto flex flex-col bg-[#FAFAFA]">

        {/* Header with Search and Actions */}
        <header className="bg-card border-b border-border px-8 py-5 flex items-center justify-between sticky top-0 z-20 shadow-sm">
          <div className="flex items-center gap-4 bg-[#F4F4F5] px-4 py-2 rounded-xl w-96 border border-border">
            <Search className="w-4 h-4 text-txt-muted" />
            <input
              type="text"
              placeholder="Search jobs, skills, or companies..."
              className="bg-transparent border-none outline-none text-sm text-txt-primary placeholder-txt-muted w-full"
            />
          </div>

          <div className="flex items-center gap-3">
            <select
              value={filterPlatform}
              onChange={e => setFilterPlatform(e.target.value)}
              className="input-field text-sm rounded-xl px-3 py-2 text-txt-secondary border border-border"
            >
              <option value="">All Platforms</option>
              <option value="linkedin">LinkedIn</option>
              <option value="indeed">Indeed</option>
              <option value="naukri">Naukri</option>
              <option value="instahyre">InstaHyre</option>
            </select>
            <button
              onClick={() => setAddJobOpen(true)}
              className="flex items-center gap-1.5 text-sm px-4 py-2 rounded-xl bg-card border border-border text-txt-secondary hover:border-accent hover:text-accent tracking-wide transition-all font-medium shadow-sm"
            >
              <Plus className="w-4 h-4" /> Add Manual
            </button>
          </div>
        </header>

        <div className="p-8 max-w-7xl mx-auto w-full space-y-8">

          {/* Top Hero Section */}
          <section className="bg-accent rounded-3xl p-8 text-white relative overflow-hidden shadow-card">
            <div className="relative z-10 flex justify-between items-end">
              <div>
                <h2 className="text-accent-foreground/80 font-medium text-sm mb-2 tracking-wide uppercase">Total Jobs Scanned</h2>
                <div className="text-6xl font-display font-bold tracking-tight">{jobs.length}</div>
              </div>
              <div className="flex gap-4">
                <div className="bg-black/10 backdrop-blur-md rounded-2xl px-6 py-4 border border-white/10">
                  <p className="text-white/70 text-xs font-medium uppercase tracking-wider mb-1">High Matches</p>
                  <p className="text-2xl font-bold">{jobs.filter(j => j.relevance_score > 75).length}</p>
                </div>
                <div className="bg-white/10 backdrop-blur-md rounded-2xl px-6 py-4 border border-white/20">
                  <p className="text-white/80 text-xs font-medium uppercase tracking-wider mb-1">Pending Action</p>
                  <p className="text-2xl font-bold">{jobs.filter(j => j.status === 'discovered' || j.status === 'scored').length}</p>
                </div>
              </div>
            </div>
            {/* Decorative background shape echoing Sequence */}
            <div className="absolute -right-20 -top-40 w-[500px] h-[500px] bg-white/5 rounded-full blur-3xl" />
          </section>

          {/* Setup / Metrics Row */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-card rounded-3xl p-6 border border-border shadow-sm flex flex-col">
              <div className="flex justify-between items-center mb-6">
                <h3 className="font-display font-bold text-lg text-txt-primary">Scraping Activity</h3>
                <select className="text-xs text-txt-secondary bg-transparent border-none outline-none cursor-pointer">
                  <option>Last 7 Days</option>
                </select>
              </div>
              <div className="flex-1 min-h-[200px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} dy={10} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} />
                    <Tooltip
                      cursor={{ fill: '#F3F4F6' }}
                      contentStyle={{ borderRadius: '12px', border: '1px solid #E5E7EB', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                    />
                    <Bar dataKey="jobs" fill="#0d7f6c" radius={[4, 4, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="space-y-6">
              <div className="bg-card rounded-3xl p-6 border border-border shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-txt-muted mb-1">Applied</p>
                  <p className="text-3xl font-display font-bold text-txt-primary">{applied}</p>
                </div>
                <div className="w-12 h-12 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center">
                  <Send className="w-6 h-6" />
                </div>
              </div>
              <div className="bg-card rounded-3xl p-6 border border-border shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-txt-muted mb-1">Interviews</p>
                  <p className="text-3xl font-display font-bold text-txt-primary">{interviewing}</p>
                </div>
                <div className="w-12 h-12 bg-emerald-50 text-emerald-500 rounded-full flex items-center justify-center">
                  <MessageSquare className="w-6 h-6" />
                </div>
              </div>
              <div className="bg-card rounded-3xl p-6 border border-border shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-txt-muted mb-1">Offers</p>
                  <p className="text-3xl font-display font-bold text-txt-primary">{offers}</p>
                </div>
                <div className="w-12 h-12 bg-gold/10 text-gold rounded-full flex items-center justify-center">
                  <Award className="w-6 h-6" />
                </div>
              </div>
            </div>
          </section>

          {/* Recent Activity Table */}
          <section className="bg-card rounded-3xl border border-border shadow-sm overflow-hidden flex flex-col">
            <div className="p-6 border-b border-border flex justify-between items-center">
              <h3 className="font-display font-bold text-lg text-txt-primary">Recent Pipeline Activity</h3>
              <button className="text-sm text-accent hover:text-accent-2 font-medium transition-colors">View All</button>
            </div>

            {loading ? (
              <div className="p-12 text-center text-txt-muted text-sm">Loading jobs...</div>
            ) : filtered.length === 0 ? (
              <div className="p-12 text-center text-txt-muted text-sm">No jobs match your criteria.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#F8FAFC] border-b border-border text-xs font-semibold text-txt-muted uppercase tracking-wider">
                      <th className="p-4 font-medium">Status</th>
                      <th className="p-4 font-medium">Job Details</th>
                      <th className="p-4 font-medium text-center">Match Score</th>
                      <th className="p-4 font-medium">Platform</th>
                      <th className="p-4 font-medium">Date Discovered</th>
                      <th className="p-4 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(job => (
                      <JobTableRow
                        key={job.id}
                        job={job}
                        onStatusChange={handleStatusChange}
                        onGenerate={handleGenerate}
                        generating={generating === job.id}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        {/* Add Manual Job Modal */}
        {addJobOpen && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
            <div className="bg-card rounded-3xl w-full max-w-lg shadow-2xl border border-border animate-fade-in-up overflow-hidden">
              <div className="p-6 border-b border-border flex items-center justify-between bg-[#F8FAFC]">
                <div>
                  <h2 className="font-display font-bold text-xl text-txt-primary">Add Job Manually</h2>
                  <p className="text-sm text-txt-muted mt-1">Paste any job description for AI analysis</p>
                </div>
                <button onClick={() => setAddJobOpen(false)} className="p-2 rounded-xl hover:bg-black/5 text-txt-muted hover:text-txt-primary transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-6 space-y-4">
                {(['title', 'company', 'url', 'location'] as const).map(field => (
                  <div key={field}>
                    <label className="text-xs font-semibold uppercase tracking-wider text-txt-muted block mb-2">
                      {field}
                    </label>
                    <input
                      value={manualForm[field] as string}
                      onChange={e => setManualForm(prev => ({ ...prev, [field]: e.target.value }))}
                      placeholder={field === 'url' ? 'https://…' : `Enter ${field}`}
                      className="input-field w-full rounded-xl px-4 py-3 text-sm border-border focus:border-accent"
                    />
                  </div>
                ))}
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider text-txt-muted block mb-2">
                    Job Description
                  </label>
                  <textarea
                    value={manualForm.jd_text}
                    onChange={e => setManualForm(prev => ({ ...prev, jd_text: e.target.value }))}
                    rows={5}
                    placeholder="Paste the full job description here…"
                    className="input-field w-full rounded-xl px-4 py-3 text-sm resize-none border-border focus:border-accent"
                  />
                </div>
              </div>
              <div className="p-6 border-t border-border flex gap-3 justify-end bg-[#F8FAFC]">
                <button
                  onClick={() => setAddJobOpen(false)}
                  className="px-5 py-2.5 text-sm border border-border text-txt-secondary hover:bg-black/5 hover:text-txt-primary rounded-xl transition-all font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddManual}
                  className="px-5 py-2.5 text-sm bg-accent hover:bg-opacity-90 text-white rounded-xl font-semibold transition-all shadow-md"
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

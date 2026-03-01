'use client';

import Sidebar from '../components/Sidebar';
import { useEffect, useState } from 'react';
import {
    BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip,
    ResponsiveContainer
} from 'recharts';
import { TrendingUp, Briefcase, CheckSquare, Award, Activity } from 'lucide-react';

const API = 'http://localhost:8000';

const STATUS_COLORS: Record<string, string> = {
    discovered: '#6366f1', scored: '#8b5cf6', tailored: '#3b82f6',
    applied: '#0ea5e9', interviewing: '#10b981', rejected: '#ef4444', offer: '#f59e0b',
};

const PLATFORM_COLORS: Record<string, string> = {
    linkedin: '#60a5fa', indeed: '#818cf8', naukri: '#fb923c',
    instahyre: '#a78bfa', manual: '#94a3b8',
};

interface Analytics {
    total_jobs: number;
    by_status: Record<string, number>;
    by_platform: Record<string, number>;
    top_companies: { company: string; score: number }[];
}

function StatCard({ label, value, icon: Icon, sub, color = '#6366f1' }: {
    label: string; value: number | string; icon: React.ElementType; sub?: string; color?: string;
}) {
    return (
        <div className="glass rounded-2xl p-5 border border-border group hover:border-border-bright transition-all">
            <div className="flex items-start justify-between mb-3">
                <p className="text-xs font-semibold uppercase tracking-widest text-txt-muted">{label}</p>
                <div className="p-2 rounded-lg" style={{ background: `${color}20` }}>
                    <Icon className="w-4 h-4" style={{ color }} />
                </div>
            </div>
            <p className="font-display font-bold text-3xl text-txt-primary">{value}</p>
            {sub && <p className="text-xs text-txt-muted mt-1">{sub}</p>}
        </div>
    );
}

const TooltipStyle = {
    background: '#111827',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '8px',
    color: '#f0f4ff',
    fontFamily: 'Inter',
    fontSize: '12px',
};

export default function AnalyticsPage() {
    const [data, setData] = useState<Analytics | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${API}/api/analytics`)
            .then(r => r.json())
            .then(d => { setData(d); setLoading(false); })
            .catch(() => setLoading(false));
    }, []);

    const statusData = data ? Object.entries(data.by_status)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => ({ name: k.charAt(0).toUpperCase() + k.slice(1), value: v, color: STATUS_COLORS[k] || '#888' })) : [];

    const platformData = data ? Object.entries(data.by_platform)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => ({ name: k.charAt(0).toUpperCase() + k.slice(1), value: v, fill: PLATFORM_COLORS[k] || '#888' })) : [];

    const applied = data?.by_status['applied'] || 0;
    const interviews = data?.by_status['interviewing'] || 0;
    const offers = data?.by_status['offer'] || 0;
    const responseRate = applied > 0 ? Math.round(((interviews + offers) / applied) * 100) : 0;

    return (
        <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto">
                <header className="glass border-b border-border px-6 py-4 sticky top-0 z-20">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-accent/10">
                            <Activity className="w-5 h-5 text-accent-light" />
                        </div>
                        <div>
                            <h1 className="font-display font-bold text-2xl text-txt-primary">Analytics</h1>
                            <p className="text-xs text-txt-muted">Application performance & insights</p>
                        </div>
                    </div>
                </header>

                {loading ? (
                    <div className="flex-1 flex items-center justify-center h-[80vh]">
                        <div className="text-center space-y-3">
                            <div className="w-10 h-10 rounded-full border-2 border-accent border-t-transparent animate-spin mx-auto" />
                            <p className="text-txt-muted text-sm">Compiling metrics…</p>
                        </div>
                    </div>
                ) : (
                    <div className="p-6 max-w-5xl mx-auto space-y-6">
                        {/* Stat cards */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <StatCard label="Total Jobs" value={data?.total_jobs || 0} icon={Briefcase} sub="In your pipeline" color="#6366f1" />
                            <StatCard label="Applied" value={applied} icon={CheckSquare} sub="Submissions made" color="#0ea5e9" />
                            <StatCard label="Interviewing" value={interviews} icon={TrendingUp} sub="Active processes" color="#10b981" />
                            <StatCard label="Response Rate" value={`${responseRate}%`} icon={Award} sub="Interviews ÷ Applied" color="#f59e0b" />
                        </div>

                        {/* Charts */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            {/* Status pie */}
                            <div className="glass rounded-2xl border border-border p-5">
                                <h2 className="font-display font-semibold text-base text-txt-primary mb-1">Pipeline Status</h2>
                                <p className="text-xs text-txt-muted mb-4">Distribution across stages</p>
                                <ResponsiveContainer width="100%" height={220}>
                                    <PieChart>
                                        <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                                            outerRadius={80} innerRadius={35}
                                            label={({ name, value }) => `${name}: ${value}`} labelLine={false}>
                                            {statusData.map((entry, i) => (
                                                <Cell key={i} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <Tooltip contentStyle={TooltipStyle} />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Platform bar */}
                            <div className="glass rounded-2xl border border-border p-5">
                                <h2 className="font-display font-semibold text-base text-txt-primary mb-1">By Platform</h2>
                                <p className="text-xs text-txt-muted mb-4">Jobs sourced per platform</p>
                                <ResponsiveContainer width="100%" height={220}>
                                    <BarChart data={platformData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#8892a4' }} axisLine={false} tickLine={false} />
                                        <YAxis tick={{ fontSize: 11, fill: '#8892a4' }} axisLine={false} tickLine={false} />
                                        <Tooltip contentStyle={TooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                                        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                                            {platformData.map((entry, i) => (
                                                <Cell key={i} fill={entry.fill} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Top companies */}
                        {data?.top_companies && data.top_companies.length > 0 && (
                            <div className="glass rounded-2xl border border-border p-5">
                                <h2 className="font-display font-semibold text-base text-txt-primary mb-1">Top Scoring Opportunities</h2>
                                <p className="text-xs text-txt-muted mb-4">Highest AI relevance scores</p>
                                <div className="space-y-3">
                                    {data.top_companies.map((c, i) => {
                                        const col = c.score >= 75 ? '#10b981' : c.score >= 50 ? '#f59e0b' : '#ef4444';
                                        return (
                                            <div key={i} className="flex items-center gap-3">
                                                <span className="font-mono text-xs text-txt-muted w-5 text-right">{i + 1}</span>
                                                <div className="flex-1">
                                                    <div className="flex justify-between mb-1">
                                                        <span className="font-medium text-sm text-txt-primary">{c.company}</span>
                                                        <span className="font-mono text-xs font-bold" style={{ color: col }}>{Math.round(c.score)}/100</span>
                                                    </div>
                                                    <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                                                        <div className="h-full rounded-full transition-all" style={{ width: `${c.score}%`, background: col }} />
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}

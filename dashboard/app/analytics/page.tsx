'use client';

import Sidebar from '../components/Sidebar';
import { useEffect, useState } from 'react';
import {
    BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip,
    ResponsiveContainer, Legend
} from 'recharts';
import { TrendingUp, Briefcase, CheckSquare, Award } from 'lucide-react';

const API = 'http://localhost:8000';

const STATUS_COLORS: Record<string, string> = {
    discovered: '#5c4d3a',
    scored: '#b8860b',
    tailored: '#6c63ff',
    applied: '#003A9B',
    interviewing: '#2d6a2d',
    rejected: '#8b1a1a',
    offer: '#d4a017',
};

const PLATFORM_COLORS: Record<string, string> = {
    linkedin: '#0077B5',
    indeed: '#003A9B',
    naukri: '#ff7555',
    instahyre: '#6c63ff',
    manual: '#5c4d3a',
};

interface Analytics {
    total_jobs: number;
    by_status: Record<string, number>;
    by_platform: Record<string, number>;
    top_companies: { company: string; score: number }[];
}

function StatCard({ label, value, icon: Icon, sub }: { label: string; value: number | string; icon: React.ElementType; sub?: string }) {
    return (
        <div className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-4">
            <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-sans uppercase tracking-widest text-ink-muted">{label}</p>
                <Icon className="w-4 h-4 text-accent-gold" />
            </div>
            <p className="font-serif font-black text-4xl text-ink">{value}</p>
            {sub && <p className="text-xs text-ink-muted mt-1">{sub}</p>}
        </div>
    );
}

export default function AnalyticsPage() {
    const [data, setData] = useState<Analytics | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${API}/api/analytics`)
            .then(r => r.json())
            .then(d => { setData(d); setLoading(false); })
            .catch(() => setLoading(false));
    }, []);

    if (loading) return (
        <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 flex items-center justify-center">
                <p className="font-serif text-2xl animate-pulse">Compiling the press…</p>
            </main>
        </div>
    );

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
                {/* Masthead */}
                <header className="bg-newsprint border-b-4 border-double border-ink px-6 py-4 sticky top-0 z-10">
                    <h1 className="font-serif text-3xl font-black text-ink">Intelligence Bureau</h1>
                    <div className="w-full h-px bg-gradient-to-r from-ink via-accent-gold to-ink mt-1 mb-1" />
                    <p className="text-xs text-ink-muted font-sans">Application performance metrics & analytics</p>
                </header>

                <div className="p-6 max-w-5xl mx-auto space-y-8">
                    {/* Stat cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <StatCard label="Total Jobs" value={data?.total_jobs || 0} icon={Briefcase} sub="In your pipeline" />
                        <StatCard label="Applied" value={applied} icon={CheckSquare} sub="Submissions made" />
                        <StatCard label="Interviewing" value={interviews} icon={TrendingUp} sub="Active processes" />
                        <StatCard label="Response Rate" value={`${responseRate}%`} icon={Award} sub="(Interviews / Applied)" />
                    </div>

                    {/* Charts */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Status distribution */}
                        <div className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-5">
                            <h2 className="font-serif font-bold text-lg text-ink mb-1">Pipeline Status</h2>
                            <div className="h-0.5 bg-gradient-to-r from-ink/40 to-transparent mb-4" />
                            <ResponsiveContainer width="100%" height={220}>
                                <PieChart>
                                    <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`} labelLine={false}>
                                        {statusData.map((entry, i) => (
                                            <Cell key={i} fill={entry.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip contentStyle={{ background: '#f5f0e8', border: '1px solid #1a1209', fontFamily: 'serif' }} />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Platform breakdown */}
                        <div className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-5">
                            <h2 className="font-serif font-bold text-lg text-ink mb-1">By Platform</h2>
                            <div className="h-0.5 bg-gradient-to-r from-ink/40 to-transparent mb-4" />
                            <ResponsiveContainer width="100%" height={220}>
                                <BarChart data={platformData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                                    <XAxis dataKey="name" tick={{ fontSize: 11, fontFamily: 'serif' }} />
                                    <YAxis tick={{ fontSize: 11, fontFamily: 'mono' }} />
                                    <Tooltip contentStyle={{ background: '#f5f0e8', border: '1px solid #1a1209', fontFamily: 'serif' }} />
                                    <Bar dataKey="value" radius={[3, 3, 0, 0]}>
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
                        <div className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-5">
                            <h2 className="font-serif font-bold text-lg text-ink mb-1">Top Scoring Opportunities</h2>
                            <div className="h-0.5 bg-gradient-to-r from-ink/40 to-transparent mb-4" />
                            <div className="space-y-2">
                                {data.top_companies.map((c, i) => (
                                    <div key={i} className="flex items-center gap-3">
                                        <span className="font-mono text-xs text-ink-muted w-5">{i + 1}</span>
                                        <div className="flex-1 bg-newsprint-dark rounded-full h-2 overflow-hidden">
                                            <div
                                                className="h-full rounded-full transition-all"
                                                style={{ width: `${c.score}%`, background: c.score >= 75 ? '#2d6a2d' : c.score >= 50 ? '#b8860b' : '#8b1a1a' }}
                                            />
                                        </div>
                                        <span className="font-serif font-semibold text-sm text-ink flex-1">{c.company}</span>
                                        <span className="font-mono text-xs font-bold" style={{ color: c.score >= 75 ? '#2d6a2d' : c.score >= 50 ? '#b8860b' : '#8b1a1a' }}>
                                            {Math.round(c.score)}/100
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}

'use client';

import Sidebar from '../components/Sidebar';
import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Copy, Check, Mail, MessageSquare, FileText, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';

const API = 'http://localhost:8000';

interface AppMaterials {
    cold_email: string;
    linkedin_message: string;
    cover_letter: string;
    tailored_resume_text: string;
    notes: string;
}

interface Job {
    id: string;
    title: string;
    company: string;
    platform: string;
    relevance_score: number;
    status: string;
}

function CopyButton({ text }: { text: string }) {
    const [copied, setCopied] = useState(false);
    const handleCopy = () => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };
    return (
        <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs px-2.5 py-1 border border-border text-txt-muted hover:border-accent/50 hover:text-accent-light rounded-lg transition-all"
        >
            {copied ? <Check className="w-3 h-3 text-emerald" /> : <Copy className="w-3 h-3" />}
            {copied ? 'Copied!' : 'Copy'}
        </button>
    );
}

function TextBlock({ label, icon: Icon, content, monospace = false }: {
    label: string; icon: React.ElementType; content: string; monospace?: boolean;
}) {
    const [expanded, setExpanded] = useState(true);
    if (!content) return null;
    return (
        <div className="glass rounded-2xl border border-border overflow-hidden">
            <div
                className="flex items-center justify-between px-4 py-3 border-b border-border cursor-pointer select-none hover:bg-white/3 transition-colors"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-accent-light" />
                    <span className="font-display font-semibold text-sm text-txt-primary">{label}</span>
                </div>
                <div className="flex items-center gap-2">
                    <CopyButton text={content} />
                    {expanded ? <ChevronUp className="w-4 h-4 text-txt-muted" /> : <ChevronDown className="w-4 h-4 text-txt-muted" />}
                </div>
            </div>
            {expanded && (
                <pre className={`p-4 text-sm text-txt-secondary leading-relaxed whitespace-pre-wrap ${monospace ? 'font-mono text-xs' : 'font-sans'}`}>
                    {content}
                </pre>
            )}
        </div>
    );
}

function OutreachContent() {
    const params = useSearchParams();
    const jobIdFromUrl = params.get('job') || '';

    const [jobs, setJobs] = useState<Job[]>([]);
    const [selectedJob, setSelectedJob] = useState<string>(jobIdFromUrl);
    const [materials, setMaterials] = useState<AppMaterials | null>(null);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);

    useEffect(() => {
        fetch(`${API}/api/jobs`).then(r => r.json()).then(data => {
            setJobs(data);
            if (!selectedJob && data.length > 0) setSelectedJob(data[0].id);
        }).catch(() => { });
    }, []);

    useEffect(() => {
        if (!selectedJob) return;
        setLoading(true);
        fetch(`${API}/api/applications/${selectedJob}`)
            .then(r => r.json())
            .then(data => { setMaterials(data); setLoading(false); })
            .catch(() => { setMaterials(null); setLoading(false); });
    }, [selectedJob]);

    const handleGenerate = async () => {
        if (!selectedJob) return;
        setGenerating(true);
        await fetch(`${API}/api/applications/${selectedJob}/generate`, { method: 'POST' });
        let attempts = 0;
        const poll = setInterval(async () => {
            attempts++;
            try {
                const r = await fetch(`${API}/api/applications/${selectedJob}`);
                const data = await r.json();
                if (data.cold_email) {
                    setMaterials(data); setGenerating(false); clearInterval(poll);
                }
            } catch { }
            if (attempts > 20) { setGenerating(false); clearInterval(poll); }
        }, 3000);
    };

    const selectedJobData = jobs.find(j => j.id === selectedJob);

    return (
        <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto">
                <header className="glass border-b border-border px-6 py-4 sticky top-0 z-20">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-accent/10">
                            <Mail className="w-5 h-5 text-accent-light" />
                        </div>
                        <div>
                            <h1 className="font-display font-bold text-2xl text-txt-primary">Outreach</h1>
                            <p className="text-xs text-txt-muted">AI-generated emails · messages · cover letters</p>
                        </div>
                    </div>
                </header>

                <div className="p-6 max-w-4xl mx-auto space-y-5">
                    {/* Job selector */}
                    <div className="glass rounded-2xl border border-border p-5">
                        <label className="text-xs font-semibold uppercase tracking-widest text-txt-muted block mb-2">
                            Select Job
                        </label>
                        <select
                            value={selectedJob}
                            onChange={e => setSelectedJob(e.target.value)}
                            className="input-field w-full rounded-xl px-3 py-2 text-sm"
                        >
                            <option value="">— Choose a job —</option>
                            {jobs.map(j => (
                                <option key={j.id} value={j.id} style={{ background: '#111827' }}>
                                    [{Math.round(j.relevance_score)}] {j.company} · {j.title} ({j.platform})
                                </option>
                            ))}
                        </select>

                        {selectedJobData && (
                            <div className="mt-4 flex items-center justify-between">
                                <div>
                                    <p className="font-display font-semibold text-txt-primary">{selectedJobData.title}</p>
                                    <p className="text-sm text-txt-muted">{selectedJobData.company} · Score: {Math.round(selectedJobData.relevance_score)}/100</p>
                                </div>
                                <button
                                    onClick={handleGenerate}
                                    disabled={generating}
                                    className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-2 text-white rounded-xl font-semibold text-sm transition-all shadow-glow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {generating ? <span className="animate-spin">↺</span> : <Sparkles className="w-4 h-4" />}
                                    {generating ? 'Generating…' : 'Generate All Materials'}
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Materials */}
                    {loading ? (
                        <div className="text-center py-16">
                            <div className="w-8 h-8 border-2 border-accent border-t-transparent animate-spin rounded-full mx-auto mb-4" />
                            <p className="text-txt-muted text-sm">Loading materials…</p>
                        </div>
                    ) : materials ? (
                        <div className="space-y-3 animate-fade-in-up">
                            <TextBlock label="Cold Email" icon={Mail} content={materials.cold_email} />
                            <TextBlock label="LinkedIn Message" icon={MessageSquare} content={materials.linkedin_message} />
                            <TextBlock label="Cover Letter" icon={FileText} content={materials.cover_letter} />
                            {materials.tailored_resume_text && (
                                <TextBlock label="Tailored Resume (LaTeX)" icon={FileText} content={materials.tailored_resume_text} monospace />
                            )}
                        </div>
                    ) : selectedJob ? (
                        <div className="text-center py-16 border border-dashed border-border rounded-2xl">
                            <Sparkles className="w-10 h-10 text-txt-muted mx-auto mb-3" />
                            <p className="text-txt-secondary font-display font-semibold text-lg mb-1">No materials yet</p>
                            <p className="text-txt-muted text-sm">Click "Generate All Materials" above</p>
                        </div>
                    ) : (
                        <div className="text-center py-16">
                            <p className="text-txt-muted">Select a job to view outreach materials</p>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}

export default function OutreachPage() {
    return (
        <Suspense fallback={
            <div className="flex min-h-screen">
                <Sidebar />
                <main className="flex-1 flex items-center justify-center">
                    <div className="w-8 h-8 border-2 border-accent border-t-transparent animate-spin rounded-full" />
                </main>
            </div>
        }>
            <OutreachContent />
        </Suspense>
    );
}

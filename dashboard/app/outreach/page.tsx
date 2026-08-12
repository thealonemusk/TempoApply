'use client';

import Sidebar from '../components/Sidebar';
import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Copy, Check, Mail, MessageSquare, FileText, ChevronDown, ChevronUp } from 'lucide-react';

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
            className="flex items-center gap-1 text-xs px-2 py-1 border border-accent-gold text-accent-gold rounded hover:bg-accent-gold hover:text-ink transition-colors"
        >
            {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
            {copied ? 'Copied!' : 'Copy'}
        </button>
    );
}

function TextBlock({ label, icon: Icon, content, monospace = false }: {
    label: string;
    icon: React.ElementType;
    content: string;
    monospace?: boolean;
}) {
    const [expanded, setExpanded] = useState(true);
    if (!content) return null;
    return (
        <div className="border border-newsprint-dark rounded overflow-hidden">
            <div
                className="flex items-center justify-between px-4 py-2 bg-newsprint-dark border-b border-newsprint-darker cursor-pointer select-none"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-accent-gold" />
                    <span className="font-serif font-bold text-sm text-ink">{label}</span>
                </div>
                <div className="flex items-center gap-2">
                    <CopyButton text={content} />
                    {expanded ? <ChevronUp className="w-4 h-4 text-ink-muted" /> : <ChevronDown className="w-4 h-4 text-ink-muted" />}
                </div>
            </div>
            {expanded && (
                <pre className={`p-4 text-sm text-ink leading-relaxed whitespace-pre-wrap bg-newsprint ${monospace ? 'font-mono text-xs' : 'font-sans'}`}>
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
        // Poll for completion
        let attempts = 0;
        const poll = setInterval(async () => {
            attempts++;
            try {
                const r = await fetch(`${API}/api/applications/${selectedJob}`);
                const data = await r.json();
                if (data.cold_email) {
                    setMaterials(data);
                    setGenerating(false);
                    clearInterval(poll);
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
                {/* Masthead */}
                <header className="bg-newsprint border-b-4 border-double border-ink px-6 py-4 sticky top-0 z-10">
                    <h1 className="font-serif text-3xl font-black text-ink">Outreach Centre</h1>
                    <div className="w-full h-px bg-gradient-to-r from-ink via-accent-gold to-ink mt-1 mb-1" />
                    <p className="text-xs text-ink-muted font-sans">AI-generated cold emails · LinkedIn messages · Cover letters</p>
                </header>

                <div className="p-6 max-w-4xl mx-auto space-y-6">
                    {/* Job selector */}
                    <div className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-4">
                        <label className="text-xs font-semibold uppercase tracking-widest text-ink-muted block mb-2">
                            Select Job
                        </label>
                        <select
                            value={selectedJob}
                            onChange={e => setSelectedJob(e.target.value)}
                            className="w-full border border-newsprint-dark rounded bg-newsprint px-3 py-2 text-sm focus:outline-none focus:border-accent-gold font-serif"
                        >
                            <option value="">— Choose a job —</option>
                            {jobs.map(j => (
                                <option key={j.id} value={j.id}>
                                    [{Math.round(j.relevance_score)}] {j.company} · {j.title} ({j.platform})
                                </option>
                            ))}
                        </select>

                        {selectedJobData && (
                            <div className="mt-3 flex items-center justify-between">
                                <div>
                                    <p className="font-serif font-bold">{selectedJobData.title}</p>
                                    <p className="text-sm text-ink-muted">{selectedJobData.company} — Score: {Math.round(selectedJobData.relevance_score)}/100</p>
                                </div>
                                <button
                                    onClick={handleGenerate}
                                    disabled={generating}
                                    className="flex items-center gap-2 px-4 py-2 bg-accent-gold text-ink rounded font-semibold text-sm hover:bg-accent-gold-light transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {generating ? <span className="animate-spin">⟳</span> : '✦'}
                                    {generating ? 'Generating…' : 'Generate All Materials'}
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Materials */}
                    {loading ? (
                        <div className="text-center py-12">
                            <p className="font-serif text-xl animate-pulse">Typesetting your outreach…</p>
                        </div>
                    ) : materials ? (
                        <div className="space-y-4 animate-fade-in-up">
                            <TextBlock label="Cold Email" icon={Mail} content={materials.cold_email} />
                            <TextBlock label="LinkedIn Message" icon={MessageSquare} content={materials.linkedin_message} />
                            <TextBlock label="Cover Letter" icon={FileText} content={materials.cover_letter} />
                            {materials.tailored_resume_text && (
                                <TextBlock label="Tailored Resume (LaTeX)" icon={FileText} content={materials.tailored_resume_text} monospace />
                            )}
                        </div>
                    ) : selectedJob ? (
                        <div className="text-center py-12 border-2 border-dashed border-newsprint-dark rounded">
                            <p className="font-serif text-xl text-ink-muted mb-4">No materials generated yet</p>
                            <p className="text-sm text-ink-muted mb-4">Click "Generate All Materials" above to create tailored outreach for this job.</p>
                        </div>
                    ) : (
                        <div className="text-center py-12">
                            <p className="font-serif text-xl text-ink-muted">Select a job to view outreach materials</p>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}

export default function OutreachPage() {
    return (
        <Suspense fallback={<div className="flex min-h-screen"><Sidebar /><main className="flex-1 flex items-center justify-center"><p className="font-serif text-xl animate-pulse">Loading…</p></main></div>}>
            <OutreachContent />
        </Suspense>
    );
}

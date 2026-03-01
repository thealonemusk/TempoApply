'use client';

import Sidebar from '../components/Sidebar';
import { useState, useEffect } from 'react';
import { Upload, FileText, CheckCircle, Info } from 'lucide-react';
import clsx from 'clsx';

const API = 'http://localhost:8000';

export default function ResumePage() {
    const [activeResume, setActiveResume] = useState<any>(null);
    const [uploading, setUploading] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const [message, setMessage] = useState('');
    const [msgOk, setMsgOk] = useState(true);

    const fetchResume = async () => {
        try {
            const r = await fetch(`${API}/api/resume/active`);
            const d = await r.json();
            setActiveResume(d.resume ? null : d);
        } catch { }
    };

    useEffect(() => { fetchResume(); }, []);

    const handleUpload = async (file: File) => {
        if (!file.name.endsWith('.tex')) {
            setMsgOk(false);
            setMessage('Only .tex files are supported');
            return;
        }
        setUploading(true);
        const form = new FormData();
        form.append('file', file);
        try {
            const r = await fetch(`${API}/api/resume/upload`, { method: 'POST', body: form });
            const d = await r.json();
            setMsgOk(true);
            setMessage(`Resume uploaded: ${d.filename} (${d.preview_chars} chars parsed)`);
            fetchResume();
        } catch {
            setMsgOk(false);
            setMessage('Upload failed. Is the API running?');
        }
        setUploading(false);
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleUpload(file);
    };

    return (
        <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto">
                <header className="glass border-b border-border px-6 py-4 sticky top-0 z-20">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-accent/10">
                            <FileText className="w-5 h-5 text-accent-light" />
                        </div>
                        <div>
                            <h1 className="font-display font-bold text-2xl text-txt-primary">Resume</h1>
                            <p className="text-xs text-txt-muted">Upload your base .tex · AI tailors it per job</p>
                        </div>
                    </div>
                </header>

                <div className="p-6 max-w-3xl mx-auto space-y-5">
                    {/* Upload zone */}
                    <div
                        onDrop={handleDrop}
                        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                        onDragLeave={() => setDragOver(false)}
                        onClick={() => document.getElementById('resumeFileInput')?.click()}
                        className={clsx(
                            'border-2 border-dashed rounded-2xl p-14 text-center cursor-pointer transition-all',
                            dragOver
                                ? 'border-accent bg-accent/5 shadow-glow'
                                : 'border-border hover:border-accent/40 hover:bg-white/2'
                        )}
                    >
                        <input
                            id="resumeFileInput" type="file" accept=".tex"
                            className="hidden"
                            onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])}
                        />
                        <div className="flex flex-col items-center gap-3">
                            {uploading ? (
                                <>
                                    <div className="w-12 h-12 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                                    <p className="font-display font-semibold text-txt-primary">Uploading…</p>
                                </>
                            ) : (
                                <>
                                    <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center">
                                        <Upload className="w-7 h-7 text-accent-light" />
                                    </div>
                                    <div>
                                        <p className="font-display font-semibold text-lg text-txt-primary">Drop your .tex resume</p>
                                        <p className="text-sm text-txt-muted mt-1">or click to browse files</p>
                                    </div>
                                    <span className="text-xs bg-accent/10 text-accent-light border border-accent/30 px-3 py-1 rounded-full font-semibold uppercase tracking-wide">
                                        .tex files only
                                    </span>
                                </>
                            )}
                        </div>
                    </div>

                    {/* Message */}
                    {message && (
                        <div className={clsx(
                            'flex items-center gap-2 p-3 rounded-xl text-sm border',
                            msgOk
                                ? 'bg-emerald/10 border-emerald/30 text-emerald'
                                : 'bg-danger/10 border-danger/30 text-danger'
                        )}>
                            {msgOk ? <CheckCircle className="w-4 h-4 flex-shrink-0" /> : <Info className="w-4 h-4 flex-shrink-0" />}
                            {message}
                        </div>
                    )}

                    {/* Active resume */}
                    {activeResume?.resume_id && (
                        <div className="glass rounded-2xl border border-border p-5 animate-fade-in-up">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="p-2 rounded-lg bg-emerald/10">
                                    <CheckCircle className="w-5 h-5 text-emerald" />
                                </div>
                                <div>
                                    <h2 className="font-display font-semibold text-txt-primary">Active Resume</h2>
                                    <p className="text-sm text-txt-muted">{activeResume.filename}</p>
                                </div>
                                <p className="ml-auto text-xs text-txt-muted">
                                    {activeResume.uploaded_at ? new Date(activeResume.uploaded_at).toLocaleDateString() : '—'}
                                </p>
                            </div>
                            <div className="h-px bg-border mb-4" />
                            <p className="text-xs font-mono text-txt-muted mb-2 uppercase tracking-widest">Preview (parsed LaTeX):</p>
                            <pre className="text-xs font-mono text-txt-secondary bg-base rounded-xl p-4 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto border border-border">
                                {activeResume.content_preview}
                                {activeResume.content_preview ? '…' : '(No content parsed yet)'}
                            </pre>
                        </div>
                    )}

                    {/* How it works */}
                    <div className="glass rounded-2xl border border-border p-5">
                        <h3 className="font-display font-semibold text-txt-primary mb-4 flex items-center gap-2">
                            <Info className="w-4 h-4 text-accent-light" /> How It Works
                        </h3>
                        <ol className="space-y-2.5">
                            {[
                                'Upload your base .tex resume above.',
                                'Run a job scan from the sidebar to discover jobs.',
                                'Click "AI Resume" on any job card in the Pipeline.',
                                'Gemini AI tailors your resume for that job, optimizing ATS keywords.',
                                'Download tailored .tex files from the Outreach page.',
                            ].map((step, i) => (
                                <li key={i} className="flex gap-3 text-sm text-txt-secondary">
                                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-accent/15 border border-accent/30 text-accent-light text-xs flex items-center justify-center font-bold">
                                        {i + 1}
                                    </span>
                                    {step}
                                </li>
                            ))}
                        </ol>
                    </div>
                </div>
            </main>
        </div>
    );
}

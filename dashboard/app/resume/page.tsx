'use client';

import Sidebar from '../components/Sidebar';
import { useState, useEffect } from 'react';
import { Upload, FileText, CheckCircle } from 'lucide-react';

const API = 'http://localhost:8000';

export default function ResumePage() {
    const [activeResume, setActiveResume] = useState<any>(null);
    const [uploading, setUploading] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const [message, setMessage] = useState('');

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
            setMessage('⚠️ Only .tex files are supported');
            return;
        }
        setUploading(true);
        const form = new FormData();
        form.append('file', file);
        try {
            const r = await fetch(`${API}/api/resume/upload`, { method: 'POST', body: form });
            const d = await r.json();
            setMessage(`✅ Resume uploaded: ${d.filename} (${d.preview_chars} chars parsed)`);
            fetchResume();
        } catch {
            setMessage('❌ Upload failed. Is the API running?');
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
                <header className="bg-newsprint border-b-4 border-double border-ink px-6 py-4 sticky top-0 z-10">
                    <h1 className="font-serif text-3xl font-black text-ink">Resume Bureau</h1>
                    <div className="w-full h-px bg-gradient-to-r from-ink via-accent-gold to-ink mt-1 mb-1" />
                    <p className="text-xs text-ink-muted font-sans">Upload your base .tex resume · AI tailors it per job</p>
                </header>

                <div className="p-6 max-w-3xl mx-auto space-y-6">
                    {/* Upload zone */}
                    <div
                        onDrop={handleDrop}
                        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                        onDragLeave={() => setDragOver(false)}
                        onClick={() => document.getElementById('resumeFileInput')?.click()}
                        className={`border-4 border-dashed rounded-lg p-12 text-center cursor-pointer transition-all ${dragOver
                                ? 'border-accent-gold bg-accent-gold/5'
                                : 'border-newsprint-darker hover:border-accent-gold/50 bg-newsprint'
                            }`}
                    >
                        <input
                            id="resumeFileInput"
                            type="file"
                            accept=".tex"
                            className="hidden"
                            onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])}
                        />
                        <div className="flex flex-col items-center gap-3">
                            {uploading ? (
                                <>
                                    <div className="w-12 h-12 border-4 border-accent-gold border-t-transparent rounded-full animate-spin" />
                                    <p className="font-serif text-lg font-bold">Typesetting…</p>
                                </>
                            ) : (
                                <>
                                    <Upload className="w-12 h-12 text-ink-muted" />
                                    <p className="font-serif text-xl font-bold text-ink">Drop your .tex resume here</p>
                                    <p className="text-sm text-ink-muted">or click to browse</p>
                                    <span className="text-xs bg-accent-gold text-ink px-3 py-1 rounded font-semibold uppercase tracking-wide">
                                        .tex files only
                                    </span>
                                </>
                            )}
                        </div>
                    </div>

                    {message && (
                        <div className={`p-3 rounded border text-sm font-sans ${message.startsWith('✅') ? 'border-score-high/40 bg-green-50 text-score-high' : 'border-score-low/40 bg-red-50 text-score-low'}`}>
                            {message}
                        </div>
                    )}

                    {/* Active resume display */}
                    {activeResume?.resume_id && (
                        <div className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-5 animate-fade-in-up">
                            <div className="flex items-center gap-3 mb-3">
                                <CheckCircle className="w-5 h-5 text-score-high" />
                                <div>
                                    <h2 className="font-serif font-bold text-lg text-ink">Active Resume</h2>
                                    <p className="text-sm text-ink-muted">{activeResume.filename}</p>
                                </div>
                            </div>
                            <div className="h-px bg-newsprint-dark mb-3" />
                            <p className="text-xs font-mono text-ink-muted mb-2 uppercase tracking-widest">
                                Preview (parsed LaTeX):
                            </p>
                            <pre className="text-xs font-mono text-ink bg-newsprint-dark rounded p-3 whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
                                {activeResume.content_preview}
                                {activeResume.content_preview ? '…' : '(No content parsed yet)'}
                            </pre>
                            <p className="text-xs text-ink-muted mt-2 text-right">
                                Uploaded: {activeResume.uploaded_at ? new Date(activeResume.uploaded_at).toLocaleDateString() : '—'}
                            </p>
                        </div>
                    )}

                    {/* Instructions */}
                    <div className="border border-newsprint-dark rounded p-5 bg-newsprint/50">
                        <h3 className="font-serif font-bold text-base text-ink mb-3">How It Works</h3>
                        <ol className="space-y-2 text-sm text-ink-muted font-sans">
                            <li className="flex gap-3"><span className="font-bold text-accent-gold">1.</span> Upload your base .tex resume above.</li>
                            <li className="flex gap-3"><span className="font-bold text-accent-gold">2.</span> Run a job scan from the sidebar to discover jobs.</li>
                            <li className="flex gap-3"><span className="font-bold text-accent-gold">3.</span> Click "Generate AI" on any job card in the Pipeline.</li>
                            <li className="flex gap-3"><span className="font-bold text-accent-gold">4.</span> Gemini AI tailors your resume for that specific job, optimizing for ATS keywords.</li>
                            <li className="flex gap-3"><span className="font-bold text-accent-gold">5.</span> Download tailored .tex files from the Outreach page.</li>
                        </ol>
                    </div>
                </div>
            </main>
        </div>
    );
}

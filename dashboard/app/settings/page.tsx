'use client';

import Sidebar from '../components/Sidebar';
import { useState, useEffect } from 'react';
import { Save, CheckCircle, AlertTriangle, Settings } from 'lucide-react';
import clsx from 'clsx';

const API = 'http://localhost:8000';

interface SettingsData {
    target_roles: string[];
    experience_years: number;
    preferred_locations: string[];
    min_relevance_score: number;
    user_full_name: string;
    has_gemini_key: boolean;
    has_linkedin: boolean;
    has_naukri: boolean;
    has_indeed: boolean;
    has_instahyre: boolean;
}

function InputField({ label, value, onChange, type = 'text', placeholder = '' }: {
    label: string; value: string; onChange: (v: string) => void;
    type?: string; placeholder?: string;
}) {
    return (
        <div>
            <label className="text-xs font-semibold uppercase tracking-widest text-txt-muted block mb-1.5">{label}</label>
            <input
                type={type} value={value}
                onChange={e => onChange(e.target.value)}
                placeholder={placeholder}
                className="input-field w-full rounded-xl px-3 py-2.5 text-sm"
            />
        </div>
    );
}

function StatusIndicator({ has, label }: { has: boolean; label: string }) {
    return (
        <div className={clsx(
            'flex items-center gap-2 px-3 py-2 rounded-lg border',
            has
                ? 'bg-emerald/5 border-emerald/20 text-emerald'
                : 'bg-danger/5 border-danger/15 text-danger'
        )}>
            {has
                ? <CheckCircle className="w-3.5 h-3.5 flex-shrink-0" />
                : <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />}
            <span className="text-xs font-medium">{label}</span>
            <span className="text-xs ml-auto opacity-70">{has ? 'OK' : 'Missing'}</span>
        </div>
    );
}

const OAUTH_PLATFORMS = ['naukri', 'indeed', 'instahyre'] as const;
const ALL_PLATFORMS = ['linkedin', 'naukri', 'indeed', 'instahyre'] as const;

export default function SettingsPage() {
    const [cfg, setCfg] = useState<SettingsData | null>(null);
    const [form, setForm] = useState({
        target_roles_str: '',
        experience_years: '3',
        preferred_locations_str: '',
        min_relevance_score: '60',
        user_full_name: '',
        gemini_api_key: '',
        linkedin_email: '', linkedin_password: '',
        naukri_email: '',
        indeed_email: '',
        instahyre_email: '',
    });
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        fetch(`${API}/api/settings`)
            .then(r => r.json())
            .then(d => {
                setCfg(d);
                setForm(prev => ({
                    ...prev,
                    target_roles_str: (d.target_roles || []).join(', '),
                    experience_years: String(d.experience_years || 3),
                    preferred_locations_str: (d.preferred_locations || []).join(', '),
                    min_relevance_score: String(d.min_relevance_score || 60),
                    user_full_name: d.user_full_name || '',
                }));
            }).catch(() => { });
    }, []);

    const handleSave = async () => {
        const payload = {
            target_roles: form.target_roles_str.split(',').map(s => s.trim()).filter(Boolean),
            experience_years: parseInt(form.experience_years) || 3,
            preferred_locations: form.preferred_locations_str.split(',').map(s => s.trim()).filter(Boolean),
            min_relevance_score: parseInt(form.min_relevance_score) || 60,
            user_full_name: form.user_full_name,
            ...(form.gemini_api_key && { gemini_api_key: form.gemini_api_key }),
            ...(form.linkedin_email && { linkedin_email: form.linkedin_email }),
            ...(form.linkedin_password && { linkedin_password: form.linkedin_password }),
            ...(form.naukri_email && { naukri_email: form.naukri_email }),
            ...(form.indeed_email && { indeed_email: form.indeed_email }),
            ...(form.instahyre_email && { instahyre_email: form.instahyre_email }),
        };
        await fetch(`${API}/api/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
    };

    const f = (key: keyof typeof form) => ({
        value: form[key],
        onChange: (v: string) => setForm(p => ({ ...p, [key]: v }))
    });

    return (
        <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto">
                <header className="glass border-b border-border px-6 py-4 sticky top-0 z-20">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-accent/10">
                            <Settings className="w-5 h-5 text-accent-light" />
                        </div>
                        <div>
                            <h1 className="font-display font-bold text-2xl text-txt-primary">Settings</h1>
                            <p className="text-xs text-txt-muted">Preferences, API keys & credentials</p>
                        </div>
                    </div>
                </header>

                <div className="p-6 max-w-3xl mx-auto space-y-5 pb-12">
                    {/* Connection status */}
                    {cfg && (
                        <div className="glass rounded-2xl border border-border p-5">
                            <h2 className="font-display font-semibold text-txt-primary mb-4">Configuration Status</h2>
                            <div className="grid grid-cols-2 gap-2">
                                <StatusIndicator has={cfg.has_gemini_key} label="Gemini AI" />
                                <StatusIndicator has={cfg.has_linkedin} label="LinkedIn" />
                                <StatusIndicator has={cfg.has_naukri} label="Naukri" />
                                <StatusIndicator has={cfg.has_indeed} label="Indeed" />
                                <StatusIndicator has={cfg.has_instahyre} label="InstaHyre" />
                            </div>
                        </div>
                    )}

                    {/* Job preferences */}
                    <div className="glass rounded-2xl border border-border p-5 space-y-4">
                        <h2 className="font-display font-semibold text-txt-primary">Job Search Preferences</h2>
                        <div className="h-px bg-border" />
                        <InputField label="Your Name" {...f('user_full_name')} placeholder="Ashutosh Jha" />
                        <InputField label="Target Roles (comma-separated)" {...f('target_roles_str')} placeholder="Software Engineer, Backend Engineer" />
                        <InputField label="Preferred Locations (comma-separated)" {...f('preferred_locations_str')} placeholder="Bengaluru, Remote, Hyderabad" />
                        <div className="grid grid-cols-2 gap-4">
                            <InputField label="Years of Experience" {...f('experience_years')} type="number" placeholder="3" />
                            <InputField label="Min Relevance Score (0-100)" {...f('min_relevance_score')} type="number" placeholder="60" />
                        </div>
                    </div>

                    {/* API Keys */}
                    <div className="glass rounded-2xl border border-border p-5 space-y-4">
                        <h2 className="font-display font-semibold text-txt-primary">API Keys</h2>
                        <div className="h-px bg-border" />
                        <InputField label="Gemini API Key" {...f('gemini_api_key')} type="password" placeholder="Leave blank to keep existing" />
                    </div>

                    {/* LinkedIn */}
                    <div className="glass rounded-2xl border border-border p-5 space-y-4">
                        <h2 className="font-display font-semibold text-txt-primary">LinkedIn Credentials</h2>
                        <div className="h-px bg-border" />
                        <div className="grid grid-cols-2 gap-4">
                            <InputField label="Email" {...f('linkedin_email')} placeholder="linkedin@email.com" />
                            <InputField label="Password" {...f('linkedin_password')} type="password" placeholder="Leave blank to keep" />
                        </div>
                    </div>

                    {/* Google OAuth platforms */}
                    {OAUTH_PLATFORMS.map(p => (
                        <div key={p} className="glass rounded-2xl border border-border p-5 space-y-4">
                            <div className="flex items-center justify-between">
                                <h2 className="font-display font-semibold text-txt-primary capitalize">{p} Credentials</h2>
                                <span className="text-xs bg-accent/10 text-accent-light border border-accent/25 px-2.5 py-1 rounded-full">
                                    Google OAuth
                                </span>
                            </div>
                            <p className="text-xs text-txt-muted -mt-2">This platform uses Google Sign-In (no password required)</p>
                            <div className="h-px bg-border" />
                            <InputField label="Google Email" {...f(`${p}_email` as keyof typeof form)} placeholder={`${p}@gmail.com`} />
                        </div>
                    ))}

                    {/* Save */}
                    <div className="flex justify-end">
                        <button
                            onClick={handleSave}
                            className={clsx(
                                'flex items-center gap-2 px-6 py-2.5 rounded-xl font-semibold text-sm transition-all',
                                saved
                                    ? 'bg-emerald/10 border border-emerald/30 text-emerald'
                                    : 'bg-accent hover:bg-accent-2 text-white shadow-glow-sm'
                            )}
                        >
                            {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                            {saved ? 'Saved!' : 'Save Settings'}
                        </button>
                    </div>
                </div>
            </main>
        </div>
    );
}

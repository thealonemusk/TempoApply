'use client';

import Sidebar from '../components/Sidebar';
import { useState, useEffect } from 'react';
import { Save, CheckCircle, AlertTriangle } from 'lucide-react';

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
            <label className="text-xs font-semibold uppercase tracking-widest text-ink-muted block mb-1">{label}</label>
            <input
                type={type}
                value={value}
                onChange={e => onChange(e.target.value)}
                placeholder={placeholder}
                className="w-full border border-newsprint-dark rounded px-3 py-2 text-sm bg-newsprint focus:outline-none focus:border-accent-gold font-sans"
            />
        </div>
    );
}

function StatusIndicator({ has, label }: { has: boolean; label: string }) {
    return (
        <div className="flex items-center gap-2">
            {has
                ? <CheckCircle className="w-4 h-4 text-score-high" />
                : <AlertTriangle className="w-4 h-4 text-score-low" />}
            <span className={`text-sm font-sans ${has ? 'text-score-high' : 'text-score-low'}`}>
                {label}: {has ? 'Configured' : 'Not set'}
            </span>
        </div>
    );
}

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
        naukri_email: '', naukri_password: '',
        indeed_email: '', indeed_password: '',
        instahyre_email: '', instahyre_password: '',
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
            })
            .catch(() => { });
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
            ...(form.naukri_password && { naukri_password: form.naukri_password }),
            ...(form.indeed_email && { indeed_email: form.indeed_email }),
            ...(form.indeed_password && { indeed_password: form.indeed_password }),
            ...(form.instahyre_email && { instahyre_email: form.instahyre_email }),
            ...(form.instahyre_password && { instahyre_password: form.instahyre_password }),
        };
        await fetch(`${API}/api/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
    };

    const f = (key: keyof typeof form) => ({ value: form[key], onChange: (v: string) => setForm(p => ({ ...p, [key]: v })) });

    return (
        <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto">
                <header className="bg-newsprint border-b-4 border-double border-ink px-6 py-4 sticky top-0 z-10">
                    <h1 className="font-serif text-3xl font-black text-ink">Editorial Settings</h1>
                    <div className="w-full h-px bg-gradient-to-r from-ink via-accent-gold to-ink mt-1 mb-1" />
                    <p className="text-xs text-ink-muted font-sans">Configure your search preferences, API keys, and credentials</p>
                </header>

                <div className="p-6 max-w-3xl mx-auto space-y-6">
                    {/* Connection status */}
                    {cfg && (
                        <div className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-5">
                            <h2 className="font-serif font-bold text-base text-ink mb-3">Configuration Status</h2>
                            <div className="grid grid-cols-2 gap-2">
                                <StatusIndicator has={cfg.has_gemini_key} label="Gemini API" />
                                <StatusIndicator has={cfg.has_linkedin} label="LinkedIn" />
                                <StatusIndicator has={cfg.has_naukri} label="Naukri" />
                                <StatusIndicator has={cfg.has_indeed} label="Indeed" />
                                <StatusIndicator has={cfg.has_instahyre} label="InstaHyre" />
                            </div>
                        </div>
                    )}

                    {/* Job preferences */}
                    <div className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-5 space-y-4">
                        <h2 className="font-serif font-bold text-base text-ink">Job Search Preferences</h2>
                        <div className="h-px bg-newsprint-dark" />
                        <InputField label="Your Name" {...f('user_full_name')} placeholder="Ashutosh Jha" />
                        <InputField label="Target Roles (comma-separated)" {...f('target_roles_str')} placeholder="Software Engineer, Backend Engineer" />
                        <InputField label="Preferred Locations (comma-separated)" {...f('preferred_locations_str')} placeholder="Bengaluru, Remote, Hyderabad" />
                        <div className="grid grid-cols-2 gap-4">
                            <InputField label="Years of Experience" {...f('experience_years')} type="number" placeholder="3" />
                            <InputField label="Min Relevance Score (0-100)" {...f('min_relevance_score')} type="number" placeholder="60" />
                        </div>
                    </div>

                    {/* API Keys */}
                    <div className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-5 space-y-4">
                        <h2 className="font-serif font-bold text-base text-ink">API Keys</h2>
                        <div className="h-px bg-newsprint-dark" />
                        <InputField label="Gemini API Key" {...f('gemini_api_key')} type="password" placeholder="Leave blank to keep existing" />
                    </div>

                    {/* Platform credentials */}
                    {(['linkedin', 'naukri', 'indeed', 'instahyre'] as const).map(p => (
                        <div key={p} className="bg-newsprint border-2 border-ink rounded shadow-newspaper p-5 space-y-3">
                            <h2 className="font-serif font-bold text-base text-ink capitalize">{p} Credentials</h2>
                            <div className="h-px bg-newsprint-dark" />
                            <div className="grid grid-cols-2 gap-4">
                                <InputField label="Email" {...f(`${p}_email` as keyof typeof form)} placeholder={`${p}@email.com`} />
                                <InputField label="Password" {...f(`${p}_password` as keyof typeof form)} type="password" placeholder="Leave blank to keep" />
                            </div>
                        </div>
                    ))}

                    {/* Save */}
                    <div className="flex justify-end pb-6">
                        <button
                            onClick={handleSave}
                            className="flex items-center gap-2 px-6 py-3 bg-ink text-newsprint rounded font-serif font-bold hover:bg-ink-light transition-colors shadow-newspaper"
                        >
                            {saved ? <CheckCircle className="w-5 h-5 text-accent-gold" /> : <Save className="w-5 h-5" />}
                            {saved ? 'Saved to .env!' : 'Save Settings'}
                        </button>
                    </div>
                </div>
            </main>
        </div>
    );
}

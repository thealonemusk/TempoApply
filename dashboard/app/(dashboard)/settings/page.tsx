'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, X } from 'lucide-react';
import clsx from 'clsx';
import { api } from '@/lib/api';
import type { SettingsData } from '@/lib/types';
import { Button } from '@/components/ui/Button';
import { Card, CardDescription, CardTitle } from '@/components/ui/Card';
import { Input, Label } from '@/components/ui/Input';

export default function SettingsPage() {
  const [cfg, setCfg] = useState<SettingsData | null>(null);
  const [saved, setSaved] = useState(false);
  const [excludedCompanies, setExcludedCompanies] = useState<string[]>([]);
  const [companyInput, setCompanyInput] = useState('');
  const [form, setForm] = useState({
    target_roles_str: '',
    experience_years: '2',
    preferred_locations_str: '',
    min_relevance_score: '60',
    user_full_name: '',
    gemini_api_key: '',
    linkedin_email: '',
    linkedin_password: '',
  });

  useEffect(() => {
    api.getSettings().then((d) => {
      setCfg(d);
      setExcludedCompanies(d.excluded_companies || []);
      setForm((prev) => ({
        ...prev,
        target_roles_str: (d.target_roles || []).join(', '),
        experience_years: String(d.experience_years || 2),
        preferred_locations_str: (d.preferred_locations || []).join(', '),
        min_relevance_score: String(d.min_relevance_score || 60),
        user_full_name: d.user_full_name || '',
      }));
    }).catch(() => {});
  }, []);

  const addExcludedCompany = () => {
    const name = companyInput.trim();
    if (!name) return;
    setExcludedCompanies((prev) => {
      const lower = name.toLowerCase();
      if (prev.some((c) => c.toLowerCase() === lower)) return prev;
      return [...prev, name];
    });
    setCompanyInput('');
  };

  const removeExcludedCompany = (name: string) => {
    setExcludedCompanies((prev) => prev.filter((c) => c !== name));
  };

  const handleSave = async () => {
    await api.saveSettings({
      target_roles: form.target_roles_str.split(',').map((s) => s.trim()).filter(Boolean),
      experience_years: parseInt(form.experience_years) || 2,
      preferred_locations: form.preferred_locations_str.split(',').map((s) => s.trim()).filter(Boolean),
      min_relevance_score: parseInt(form.min_relevance_score) || 60,
      excluded_companies: excludedCompanies,
      user_full_name: form.user_full_name,
      ...(form.gemini_api_key && { gemini_api_key: form.gemini_api_key }),
      ...(form.linkedin_email && { linkedin_email: form.linkedin_email }),
      ...(form.linkedin_password && { linkedin_password: form.linkedin_password }),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleClearJobs = async () => {
    if (!confirm('Clear all discovered jobs that are not applied?')) return;
    await api.clearDiscoveredJobs();
  };

  const handlePurgeExperienced = async () => {
    if (!confirm('Remove jobs that exceed experience filters?')) return;
    await api.purgeExperiencedJobs();
  };

  const f = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((p) => ({ ...p, [key]: e.target.value })),
  });

  const connections = cfg
    ? [
        { label: 'Gemini', ok: cfg.has_gemini_key },
        { label: 'LinkedIn', ok: cfg.has_linkedin },
      ]
    : [];

  return (
    <>
      <header className="glass sticky top-0 z-20 border-b border-[var(--border)] px-8 py-5">
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">Settings</h1>
        <p className="mt-0.5 text-sm text-[var(--text-muted)]">Preferences and credentials</p>
      </header>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-2xl space-y-6 pb-12">
          <Card>
            <CardTitle>Preferences</CardTitle>
            <CardDescription>Roles and locations used during scans</CardDescription>
            <div className="mt-5 space-y-4">
              <div>
                <Label>Name</Label>
                <Input {...f('user_full_name')} />
              </div>
              <div>
                <Label>Target roles</Label>
                <Input {...f('target_roles_str')} placeholder="Software Engineer, Backend Engineer" />
              </div>
              <div>
                <Label>Locations</Label>
                <Input {...f('preferred_locations_str')} placeholder="Bengaluru, Remote" />
              </div>
              <div>
                <Label>Excluded companies</Label>
                <div className="mt-1.5 flex gap-2">
                  <Input
                    value={companyInput}
                    onChange={(e) => setCompanyInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addExcludedCompany();
                      }
                    }}
                    placeholder="TCS, Accenture, Wipro…"
                  />
                  <Button type="button" variant="secondary" onClick={addExcludedCompany}>
                    Add
                  </Button>
                </div>
                {excludedCompanies.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {excludedCompanies.map((name) => (
                      <span
                        key={name}
                        className="inline-flex items-center gap-1 rounded-full bg-[var(--surface-2)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]"
                      >
                        {name}
                        <button
                          type="button"
                          onClick={() => removeExcludedCompany(name)}
                          className="rounded-full p-0.5 text-[var(--text-muted)] hover:bg-[var(--surface-3)] hover:text-[var(--text-primary)]"
                          aria-label={`Remove ${name}`}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-[var(--text-muted)]">
                    No companies excluded. Add names to skip them during scans.
                  </p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Max experience (years)</Label>
                  <Input type="number" {...f('experience_years')} />
                </div>
                <div>
                  <Label>Min score</Label>
                  <Input type="number" {...f('min_relevance_score')} />
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <CardTitle>Connections</CardTitle>
            <CardDescription>API keys and LinkedIn sign-in</CardDescription>
            {connections.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {connections.map((c) => (
                  <span
                    key={c.label}
                    className={clsx(
                      'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium',
                      c.ok
                        ? 'bg-[var(--success-bg)] text-[var(--success)]'
                        : 'bg-[var(--surface-2)] text-[var(--text-muted)]',
                    )}
                  >
                    {c.ok && <CheckCircle className="h-3 w-3" />}
                    {c.label}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-5 space-y-4">
              <div>
                <Label>Gemini API key</Label>
                <Input type="password" {...f('gemini_api_key')} placeholder="Leave blank to keep existing" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>LinkedIn email</Label>
                  <Input {...f('linkedin_email')} />
                </div>
                <div>
                  <Label>LinkedIn password</Label>
                  <Input type="password" {...f('linkedin_password')} placeholder="Optional" />
                </div>
              </div>
            </div>
            <div className="mt-6 flex justify-end">
              <Button onClick={handleSave} className={saved ? 'bg-[var(--success)]' : ''}>
                {saved ? 'Saved' : 'Save changes'}
              </Button>
            </div>
          </Card>

          <Card className="border-[var(--danger-border)]">
            <CardTitle>Danger zone</CardTitle>
            <CardDescription>Destructive actions on your job list</CardDescription>
            <div className="mt-5 flex flex-wrap gap-3">
              <Button variant="danger" size="sm" onClick={handleClearJobs}>
                Clear discovered jobs
              </Button>
              <Button variant="danger" size="sm" onClick={handlePurgeExperienced}>
                Purge over-experienced
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}

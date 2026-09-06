'use client';

import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Circle, FileText, Upload, X } from 'lucide-react';
import clsx from 'clsx';
import { api, ApiError } from '@/lib/api';
import { useLocalState, useRunOptions } from '@/lib/hooks';
import type { ApplicantProfile, SettingsData } from '@/lib/types';
import { PageBody, PageHeader } from '@/components/PageHeader';
import { useToast } from '@/components/ui/Toast';
import {
  Button,
  Card,
  Checkbox,
  ConfirmDialog,
  Field,
  Input,
  SectionHeader,
  Select,
  Skeleton,
  Textarea,
} from '@/components/ui/Primitives';
import { Chip } from '@/components/ui/Badge';

type Tab = 'profile' | 'search' | 'run' | 'connections' | 'data';

const TABS: { key: Tab; label: string }[] = [
  { key: 'profile', label: 'Applicant profile' },
  { key: 'search', label: 'Search' },
  { key: 'run', label: 'Apply behaviour' },
  { key: 'connections', label: 'Connections' },
  { key: 'data', label: 'Data' },
];

export default function SettingsPage() {
  const toast = useToast();
  const [tab, setTab] = useLocalState<Tab>('ta.settings.tab', 'profile');

  const [cfg, setCfg] = useState<SettingsData | null>(null);
  const [profile, setProfile] = useState<Partial<ApplicantProfile>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Tab | null>(null);
  const [resumeName, setResumeName] = useState('');
  const [companyInput, setCompanyInput] = useState('');
  const [excluded, setExcluded] = useState<string[]>([]);
  const [confirm, setConfirm] = useState<null | {
    title: string;
    description: string;
    label: string;
    run: () => Promise<void>;
  }>(null);

  const [search, setSearch] = useState({
    user_full_name: '',
    target_roles_str: '',
    preferred_locations_str: '',
    experience_years: '2',
    min_relevance_score: '60',
  });

  const [secrets, setSecrets] = useState({
    gemini_api_key: '',
    linkedin_email: '',
    linkedin_password: '',
    workday_email: '',
    workday_password: '',
  });

  // Apply-run tuning is a client preference — RunControls sends it with each run.
  const [runOpts, setRunOpts] = useRunOptions();

  useEffect(() => {
    (async () => {
      try {
        const [settings, prof] = await Promise.all([api.getSettings(), api.getProfile()]);
        setCfg(settings);
        setExcluded(settings.excluded_companies ?? []);
        setSearch({
          user_full_name: settings.user_full_name ?? '',
          target_roles_str: (settings.target_roles ?? []).join(', '),
          preferred_locations_str: (settings.preferred_locations ?? []).join(', '),
          experience_years: String(settings.experience_years ?? 2),
          min_relevance_score: String(settings.min_relevance_score ?? 60),
        });
        setProfile(prof);
        if (prof.has_resume) setResumeName('resume on file');
      } catch (err) {
        toast.error(
          'Could not load settings',
          err instanceof ApiError ? err.message : 'Request failed',
        );
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pf = (key: keyof ApplicantProfile) => ({
    value: String(profile[key] ?? ''),
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setProfile((p) => ({ ...p, [key]: e.target.value })),
  });

  const guard = async (which: Tab, label: string, fn: () => Promise<void>) => {
    setSaving(which);
    try {
      await fn();
    } catch (err) {
      toast.error(label, err instanceof ApiError ? err.message : 'Request failed');
    } finally {
      setSaving(null);
    }
  };

  const saveProfile = () =>
    guard('profile', 'Could not save the profile', async () => {
      const next = await api.saveProfile({
        ...profile,
        full_name:
          `${profile.first_name ?? ''} ${profile.last_name ?? ''}`.trim() || profile.full_name,
      });
      setProfile(next);
      toast.success('Profile saved');
    });

  const saveSearch = () =>
    guard('search', 'Could not save search settings', async () => {
      await api.saveSettings({
        user_full_name: search.user_full_name,
        target_roles: split(search.target_roles_str),
        preferred_locations: split(search.preferred_locations_str),
        experience_years: Number(search.experience_years) || 2,
        min_relevance_score: Number(search.min_relevance_score) || 60,
        excluded_companies: excluded,
      });
      toast.success('Search settings saved', 'Applied immediately — no restart needed.');
    });

  const saveConnections = () =>
    guard('connections', 'Could not save connections', async () => {
      const payload = Object.fromEntries(Object.entries(secrets).filter(([, v]) => v));
      if (Object.keys(payload).length === 0) {
        toast.info('Nothing to save', 'Blank fields keep their existing values.');
        return;
      }
      await api.saveSettings(payload);
      setSecrets({
        gemini_api_key: '',
        linkedin_email: '',
        linkedin_password: '',
        workday_email: '',
        workday_password: '',
      });
      setCfg(await api.getSettings());
      toast.success('Connections saved');
    });

  const uploadResume = (file?: File) => {
    if (!file) return;
    void guard('profile', 'Resume upload failed', async () => {
      await api.uploadResume(file);
      setResumeName(file.name);
      setProfile(await api.getProfile());
      toast.success('Resume uploaded', file.name);
    });
  };

  const connections = useMemo(
    () =>
      cfg
        ? [
            { label: 'LinkedIn', ok: cfg.has_linkedin, note: 'needed for LinkedIn postings' },
            { label: 'Workday', ok: cfg.has_workday, note: 'needed for Workday applications' },
            { label: 'Gemini', ok: cfg.has_gemini_key, note: 'optional' },
            { label: 'Naukri', ok: cfg.has_naukri, note: 'optional' },
          ]
        : [],
    [cfg],
  );

  const missing = profile.missing ?? [];

  return (
    <>
      <PageHeader
        title="Settings"
        meta={
          missing.length > 0
            ? `Profile incomplete — missing ${missing.join(', ')}`
            : 'Profile complete and ready to apply'
        }
      />

      <PageBody className="space-y-4">
        {/* Tabs */}
        <div className="scroll-x -mx-1 px-1">
          <div className="inline-flex gap-1 rounded-[var(--radius)] border border-[var(--line)] bg-[var(--surface)] p-0.5">
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={clsx(
                  'whitespace-nowrap rounded-[calc(var(--radius)-2px)] px-3 py-1.5 text-[12px] font-medium transition-colors',
                  tab === key
                    ? 'bg-[var(--accent)] text-[var(--on-accent)]'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <Card className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </Card>
        ) : (
          <div className="max-w-3xl space-y-5">
            {/* ── Applicant profile ─────────────────────────────────────── */}
            {tab === 'profile' && (
              <>
                <Card>
                  <SectionHeader
                    title="Identity"
                    description="Used to fill Greenhouse, Lever, Workday and custom forms."
                  />
                  {missing.length > 0 && (
                    <p className="mb-4 rounded-[var(--radius)] bg-[var(--warn-soft)] px-3 py-2 text-[11px] text-[var(--warn)]">
                      Required before a run can start: {missing.join(', ')}
                    </p>
                  )}
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="First name">
                      <Input {...pf('first_name')} />
                    </Field>
                    <Field label="Last name">
                      <Input {...pf('last_name')} />
                    </Field>
                    <Field label="Email">
                      <Input type="email" {...pf('email')} />
                    </Field>
                    <Field label="Phone">
                      <Input {...pf('phone')} placeholder="+91 99399 64663" />
                    </Field>
                  </div>
                </Card>

                <Card>
                  <SectionHeader
                    title="Address"
                    description="Workday requires a street address and postal code."
                  />
                  <div className="space-y-3">
                    <Field label="Street address">
                      <Input {...pf('address_line1')} />
                    </Field>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <Field label="City">
                        <Input {...pf('city')} />
                      </Field>
                      <Field label="State">
                        <Input {...pf('state')} />
                      </Field>
                      <Field label="PIN / ZIP">
                        <Input {...pf('postal_code')} />
                      </Field>
                    </div>
                  </div>
                </Card>

                <Card>
                  <SectionHeader title="Links and experience" />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="LinkedIn">
                      <Input {...pf('linkedin')} />
                    </Field>
                    <Field label="GitHub">
                      <Input {...pf('github')} />
                    </Field>
                    <Field label="Portfolio" className="sm:col-span-2">
                      <Input {...pf('portfolio')} />
                    </Field>
                    <Field label="Current title">
                      <Input {...pf('current_title')} />
                    </Field>
                    <Field label="Current company">
                      <Input {...pf('current_company')} />
                    </Field>
                    <Field label="Years of experience">
                      <Input {...pf('years_experience')} />
                    </Field>
                    <Field label="Notice period">
                      <Input {...pf('notice_period')} />
                    </Field>
                    <Field label="Expected salary" className="sm:col-span-2">
                      <Input {...pf('salary_expectation')} />
                    </Field>
                    <Field label="Skills" className="sm:col-span-2">
                      <Input {...pf('skills')} />
                    </Field>
                  </div>
                </Card>

                <Card>
                  <SectionHeader title="Education" />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="School" className="sm:col-span-2">
                      <Input
                        value={profile.education?.[0]?.school ?? ''}
                        onChange={(e) =>
                          setProfile((p) => ({
                            ...p,
                            education: [
                              {
                                school: e.target.value,
                                degree: p.education?.[0]?.degree ?? 'B.Tech',
                                major: p.education?.[0]?.major ?? 'Computer Science',
                                start_year: p.education?.[0]?.start_year ?? '',
                                end_year: p.education?.[0]?.end_year ?? '',
                              },
                            ],
                          }))
                        }
                      />
                    </Field>
                    <Field label="Degree">
                      <Input
                        value={profile.education?.[0]?.degree ?? ''}
                        onChange={(e) =>
                          setProfile((p) => ({
                            ...p,
                            education: [
                              { ...(p.education?.[0] ?? emptyEdu()), degree: e.target.value },
                            ],
                          }))
                        }
                      />
                    </Field>
                    <Field label="Major">
                      <Input
                        value={profile.education?.[0]?.major ?? ''}
                        onChange={(e) =>
                          setProfile((p) => ({
                            ...p,
                            education: [
                              { ...(p.education?.[0] ?? emptyEdu()), major: e.target.value },
                            ],
                          }))
                        }
                      />
                    </Field>
                  </div>
                </Card>

                <Card>
                  <SectionHeader
                    title="Resume and cover letter"
                    description="A PDF is uploaded as-is; without one, a resume is generated from this profile."
                  />
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <label className="inline-flex cursor-pointer items-center gap-2 rounded-[var(--radius)] border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-[13px] font-medium transition-colors hover:bg-[var(--surface-hover)]">
                        <Upload className="h-3.5 w-3.5" />
                        Upload resume
                        <input
                          type="file"
                          accept=".pdf,.doc,.docx"
                          className="hidden"
                          onChange={(e) => uploadResume(e.target.files?.[0])}
                        />
                      </label>
                      {(resumeName || profile.has_resume) && (
                        <span className="inline-flex items-center gap-1.5 text-[12px] text-[var(--ink-muted)]">
                          <FileText className="h-3.5 w-3.5" />
                          {resumeName || 'resume on file'}
                        </span>
                      )}
                    </div>
                    <Field
                      label="Cover letter template"
                      hint="Placeholders: {title}, {company}, {name}"
                    >
                      <Textarea rows={5} {...pf('cover_letter_template')} />
                    </Field>
                  </div>
                </Card>

                <Card>
                  <SectionHeader title="Work authorisation" />
                  <div className="space-y-3">
                    <Checkbox
                      label="Authorised to work in India"
                      checked={!!profile.authorized_to_work}
                      onChange={(v) => setProfile((p) => ({ ...p, authorized_to_work: v }))}
                    />
                    <Checkbox
                      label="Require visa sponsorship"
                      checked={!!profile.require_sponsorship}
                      onChange={(v) => setProfile((p) => ({ ...p, require_sponsorship: v }))}
                    />
                    <Checkbox
                      label="Submit automatically once every required field is filled"
                      hint="Off means forms are filled and left for you to review and submit."
                      checked={profile.auto_submit !== false}
                      onChange={(v) => setProfile((p) => ({ ...p, auto_submit: v }))}
                    />
                  </div>
                </Card>

                <SaveBar
                  onSave={saveProfile}
                  saving={saving === 'profile'}
                  label="Save profile"
                />
              </>
            )}

            {/* ── Search ────────────────────────────────────────────────── */}
            {tab === 'search' && (
              <>
                <Card>
                  <SectionHeader
                    title="What to look for"
                    description="Drives every scraper. Saved changes apply to the next scan immediately."
                  />
                  <div className="space-y-3">
                    <Field label="Your name">
                      <Input
                        value={search.user_full_name}
                        onChange={(e) =>
                          setSearch((s) => ({ ...s, user_full_name: e.target.value }))
                        }
                      />
                    </Field>
                    <Field label="Target roles" hint="Comma separated.">
                      <Input
                        value={search.target_roles_str}
                        onChange={(e) =>
                          setSearch((s) => ({ ...s, target_roles_str: e.target.value }))
                        }
                        placeholder="Software Engineer, Backend Engineer"
                      />
                    </Field>
                    <Field label="Locations" hint="Comma separated. India-only postings are enforced.">
                      <Input
                        value={search.preferred_locations_str}
                        onChange={(e) =>
                          setSearch((s) => ({ ...s, preferred_locations_str: e.target.value }))
                        }
                        placeholder="Bengaluru, Noida, Remote"
                      />
                    </Field>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Field
                        label="Max experience (years)"
                        hint="Postings asking for more are dropped."
                      >
                        <Input
                          type="number"
                          min={0}
                          max={10}
                          value={search.experience_years}
                          onChange={(e) =>
                            setSearch((s) => ({ ...s, experience_years: e.target.value }))
                          }
                        />
                      </Field>
                      <Field label="Minimum score" hint="0–100. Lower surfaces more jobs.">
                        <Input
                          type="number"
                          min={0}
                          max={100}
                          value={search.min_relevance_score}
                          onChange={(e) =>
                            setSearch((s) => ({ ...s, min_relevance_score: e.target.value }))
                          }
                        />
                      </Field>
                    </div>
                  </div>
                </Card>

                <Card>
                  <SectionHeader
                    title="Excluded companies"
                    description="Matched as a substring of the company name during scans."
                  />
                  <div className="flex gap-2">
                    <Input
                      value={companyInput}
                      onChange={(e) => setCompanyInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key !== 'Enter') return;
                        e.preventDefault();
                        const name = companyInput.trim();
                        if (!name) return;
                        setExcluded((prev) =>
                          prev.some((c) => c.toLowerCase() === name.toLowerCase())
                            ? prev
                            : [...prev, name],
                        );
                        setCompanyInput('');
                      }}
                      placeholder="Add a company and press Enter"
                    />
                  </div>
                  {excluded.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {excluded.map((name) => (
                        <span
                          key={name}
                          className="inline-flex items-center gap-1 rounded-md bg-[var(--surface-sunken)] px-2 py-1 text-[12px] text-[var(--ink)]"
                        >
                          {name}
                          <button
                            type="button"
                            onClick={() => setExcluded((p) => p.filter((c) => c !== name))}
                            aria-label={`Remove ${name}`}
                            className="rounded p-0.5 text-[var(--ink-subtle)] hover:text-[var(--danger)]"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-[11px] text-[var(--ink-subtle)]">
                      Nothing excluded. Staffing firms are a common thing to add here.
                    </p>
                  )}
                </Card>

                <SaveBar onSave={saveSearch} saving={saving === 'search'} label="Save search" />
              </>
            )}

            {/* ── Apply behaviour ──────────────────────────────────────── */}
            {tab === 'run' && (
              <Card>
                <SectionHeader
                  title="Apply run behaviour"
                  description="Stored in this browser and sent with each run you start."
                />
                <div className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field
                      label="Parallel jobs"
                      hint={`1–${cfg?.max_concurrency ?? 4} tabs in one Chrome window.`}
                    >
                      <Select
                        value={String(runOpts.concurrency)}
                        onChange={(e) =>
                          setRunOpts({ ...runOpts, concurrency: Number(e.target.value) })
                        }
                      >
                        {Array.from({ length: cfg?.max_concurrency ?? 4 }, (_, i) => i + 1).map(
                          (n) => (
                            <option key={n} value={n}>
                              {n} {n === 1 ? 'job at a time' : 'jobs in parallel'}
                            </option>
                          ),
                        )}
                      </Select>
                    </Field>
                    <Field label="Per-job timeout" hint="A stuck posting is abandoned, not the run.">
                      <Select
                        value={String(runOpts.job_timeout_sec)}
                        onChange={(e) =>
                          setRunOpts({ ...runOpts, job_timeout_sec: Number(e.target.value) })
                        }
                      >
                        <option value="120">2 minutes</option>
                        <option value="240">4 minutes</option>
                        <option value="420">7 minutes</option>
                        <option value="900">15 minutes</option>
                      </Select>
                    </Field>
                  </div>

                  <Checkbox
                    label="Skip postings with no reachable form"
                    hint="Recommended. They are marked for manual apply instantly instead of burning a full timeout each."
                    checked={runOpts.skip_unsupported}
                    onChange={(v) => setRunOpts({ ...runOpts, skip_unsupported: v })}
                  />
                  <Checkbox
                    label="Submit automatically"
                    hint="Off fills each form and stops so you can review before submitting."
                    checked={runOpts.auto_submit}
                    onChange={(v) => setRunOpts({ ...runOpts, auto_submit: v })}
                  />
                  <Checkbox
                    label="Run Chrome headless"
                    hint="Keep this off — a visible window is how you complete a LinkedIn or Workday sign-in mid-run."
                    checked={runOpts.headless}
                    onChange={(v) => setRunOpts({ ...runOpts, headless: v })}
                  />
                </div>
              </Card>
            )}

            {/* ── Connections ──────────────────────────────────────────── */}
            {tab === 'connections' && (
              <>
                <Card>
                  <SectionHeader
                    title="Status"
                    description="Credentials live in config/.env and are never sent to the browser."
                  />
                  <ul className="space-y-2">
                    {connections.map((c) => (
                      <li key={c.label} className="flex items-center gap-2.5">
                        {c.ok ? (
                          <CheckCircle2 className="h-4 w-4 shrink-0 text-[var(--ok)]" />
                        ) : (
                          <Circle className="h-4 w-4 shrink-0 text-[var(--ink-subtle)]" />
                        )}
                        <span className="text-[13px] text-[var(--ink)]">{c.label}</span>
                        <Chip tone={c.ok ? 'ok' : 'neutral'}>{c.ok ? 'configured' : c.note}</Chip>
                      </li>
                    ))}
                  </ul>
                </Card>

                <Card>
                  <SectionHeader
                    title="Credentials"
                    description="Leave a field blank to keep its current value."
                  />
                  <div className="space-y-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Field label="LinkedIn email">
                        <Input
                          autoComplete="off"
                          value={secrets.linkedin_email}
                          onChange={(e) =>
                            setSecrets((s) => ({ ...s, linkedin_email: e.target.value }))
                          }
                        />
                      </Field>
                      <Field label="LinkedIn password">
                        <Input
                          type="password"
                          autoComplete="new-password"
                          value={secrets.linkedin_password}
                          onChange={(e) =>
                            setSecrets((s) => ({ ...s, linkedin_password: e.target.value }))
                          }
                        />
                      </Field>
                      <Field
                        label="Workday email"
                        hint="Workday reuses one candidate account per tenant."
                      >
                        <Input
                          autoComplete="off"
                          value={secrets.workday_email}
                          onChange={(e) =>
                            setSecrets((s) => ({ ...s, workday_email: e.target.value }))
                          }
                        />
                      </Field>
                      <Field label="Workday password">
                        <Input
                          type="password"
                          autoComplete="new-password"
                          value={secrets.workday_password}
                          onChange={(e) =>
                            setSecrets((s) => ({ ...s, workday_password: e.target.value }))
                          }
                        />
                      </Field>
                    </div>
                    <Field label="Gemini API key" hint="Optional — not used by the apply engine.">
                      <Input
                        type="password"
                        autoComplete="new-password"
                        value={secrets.gemini_api_key}
                        onChange={(e) =>
                          setSecrets((s) => ({ ...s, gemini_api_key: e.target.value }))
                        }
                      />
                    </Field>
                  </div>
                </Card>

                <SaveBar
                  onSave={saveConnections}
                  saving={saving === 'connections'}
                  label="Save connections"
                />
              </>
            )}

            {/* ── Data ─────────────────────────────────────────────────── */}
            {tab === 'data' && (
              <>
                <Card>
                  <SectionHeader
                    title="Maintenance"
                    description="Safe housekeeping on the job list."
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        guard('data', 'Backfill failed', async () => {
                          const { updated } = await api.backfillAts();
                          toast.success(`ATS type set on ${updated} job(s)`);
                        })
                      }
                    >
                      Detect ATS types
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        guard('data', 'Resolution failed', async () => {
                          const { checked, resolved } = await api.resolveApplyUrls();
                          toast.info(
                            `Resolved ${resolved} of ${checked}`,
                            resolved === 0
                              ? 'LinkedIn hides the employer form behind a login, so most cannot be resolved without signing in.'
                              : undefined,
                          );
                        })
                      }
                    >
                      Resolve apply links
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        guard('data', 'Purge failed', async () => {
                          const { purged_count } = await api.purgeStaleJobs();
                          toast.success(`Removed ${purged_count} stale job(s)`);
                        })
                      }
                    >
                      Purge stale
                    </Button>
                  </div>
                </Card>

                <Card className="border-[var(--danger)]">
                  <SectionHeader
                    title="Destructive"
                    description="These delete rows and cannot be undone."
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() =>
                        setConfirm({
                          title: 'Clear discovered jobs?',
                          description:
                            'Deletes every job still in discovered or scored status. Applied jobs are kept.',
                          label: 'Clear',
                          run: async () => {
                            const { deleted_count } = await api.clearDiscoveredJobs();
                            toast.success(`Deleted ${deleted_count} job(s)`);
                          },
                        })
                      }
                    >
                      Clear discovered jobs
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() =>
                        setConfirm({
                          title: 'Purge over-qualified jobs?',
                          description:
                            'Deletes jobs that fail the experience, India-location, or frontend filters.',
                          label: 'Purge',
                          run: async () => {
                            const { purged_count } = await api.purgeExperiencedJobs();
                            toast.success(`Purged ${purged_count} job(s)`);
                          },
                        })
                      }
                    >
                      Purge over-qualified
                    </Button>
                  </div>
                </Card>
              </>
            )}
          </div>
        )}
      </PageBody>

      <ConfirmDialog
        open={confirm !== null}
        title={confirm?.title ?? ''}
        description={confirm?.description}
        confirmLabel={confirm?.label}
        destructive
        busy={saving === 'data'}
        onCancel={() => setConfirm(null)}
        onConfirm={() => {
          const action = confirm;
          setConfirm(null);
          if (action) void guard('data', action.title, action.run);
        }}
      />
    </>
  );
}

function SaveBar({
  onSave,
  saving,
  label,
}: {
  onSave: () => void;
  saving: boolean;
  label: string;
}) {
  return (
    <div className="sticky bottom-4 flex justify-end">
      <Button onClick={onSave} loading={saving} className="shadow-[var(--shadow-md)]">
        {label}
      </Button>
    </div>
  );
}

function split(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

function emptyEdu() {
  return { school: '', degree: '', major: '', start_year: '', end_year: '' };
}

'use client';

import Link from 'next/link';
import { ExternalLink, Sparkles, ChevronRight } from 'lucide-react';
import clsx from 'clsx';

export type JobStatus =
    | 'discovered' | 'scored' | 'tailored'
    | 'applied' | 'interviewing' | 'rejected' | 'offer';

export interface Job {
    id: string;
    title: string;
    company: string;
    platform: string;
    url: string;
    location: string;
    relevance_score: number;
    fit_reason: string;
    seniority_level: string;
    easy_apply: boolean;
    recruiter_name: string;
    status: JobStatus;
    discovered_at: string;
}

function ScoreBadge({ score }: { score: number }) {
    const cls = score >= 75 ? 'score-high' : score >= 50 ? 'score-mid' : 'score-low';
    return (
        <span className={clsx('text-xs font-mono font-bold px-1.5 py-0.5 rounded', cls)}>
            {Math.round(score)}
        </span>
    );
}

function PlatformBadge({ platform }: { platform: string }) {
    const map: Record<string, string> = {
        linkedin: 'LI',
        indeed: 'IN',
        naukri: 'NK',
        instahyre: 'IH',
        manual: 'M',
    };
    return (
        <span className={clsx('text-xs font-bold px-1.5 py-0.5 rounded uppercase tracking-wide', `badge-${platform}`)}>
            {map[platform] || platform.slice(0, 2).toUpperCase()}
        </span>
    );
}

interface JobCardProps {
    job: Job;
    onStatusChange: (id: string, status: string) => void;
    onGenerate: (id: string) => void;
    generating?: boolean;
}

export function JobCard({ job, onStatusChange, onGenerate, generating }: JobCardProps) {
    return (
        <div className="job-card bg-newsprint border border-newsprint-dark rounded shadow-newspaper p-3 space-y-2 animate-fade-in-up">
            {/* Header */}
            <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                    <p className="font-serif font-bold text-sm text-ink leading-tight truncate">{job.title}</p>
                    <p className="text-xs text-ink-muted font-sans truncate">{job.company}</p>
                </div>
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <ScoreBadge score={job.relevance_score} />
                    <PlatformBadge platform={job.platform} />
                </div>
            </div>

            {/* Location / seniority */}
            <div className="flex items-center gap-2 flex-wrap">
                {job.location && (
                    <span className="text-xs text-ink-muted">📍 {job.location}</span>
                )}
                {job.seniority_level && (
                    <span className="text-xs bg-newsprint-dark px-1.5 py-0.5 rounded text-ink-muted capitalize">
                        {job.seniority_level}
                    </span>
                )}
                {job.easy_apply && (
                    <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded">Easy Apply</span>
                )}
            </div>

            {/* Fit reason */}
            {job.fit_reason && (
                <p className="text-xs text-ink/70 italic leading-relaxed line-clamp-2 border-l-2 border-accent-gold pl-2">
                    {job.fit_reason}
                </p>
            )}

            {/* Actions */}
            <div className="flex items-center gap-1.5 pt-1 border-t border-newsprint-dark flex-wrap">
                <a
                    href={job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs text-accent-blue hover:underline"
                >
                    <ExternalLink className="w-3 h-3" /> View
                </a>
                <button
                    onClick={() => onGenerate(job.id)}
                    disabled={generating}
                    className={clsx(
                        'flex items-center gap-1 text-xs px-2 py-0.5 rounded border transition-colors',
                        generating
                            ? 'border-accent-gold/40 text-accent-gold/40 cursor-not-allowed'
                            : 'border-accent-gold text-accent-gold hover:bg-accent-gold hover:text-ink'
                    )}
                >
                    <Sparkles className="w-3 h-3" />
                    {generating ? 'Generating…' : 'Generate AI'}
                </button>
                <Link
                    href={`/outreach?job=${job.id}`}
                    className="flex items-center gap-1 text-xs text-ink-muted hover:text-ink"
                >
                    Outreach <ChevronRight className="w-3 h-3" />
                </Link>
            </div>

            {/* Status changer */}
            <select
                value={job.status}
                onChange={(e) => onStatusChange(job.id, e.target.value)}
                className="w-full text-xs border border-newsprint-dark rounded bg-newsprint text-ink-muted py-1 px-1.5 focus:outline-none focus:border-accent-gold"
            >
                {['discovered', 'scored', 'tailored', 'applied', 'interviewing', 'rejected', 'offer'].map(s => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
            </select>
        </div>
    );
}

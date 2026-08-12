'use client';

import Link from 'next/link';
import { ExternalLink, Sparkles, ChevronRight, MapPin } from 'lucide-react';
import clsx from 'clsx';

export type JobStatus =
    | 'discovered' | 'scored' | 'tailored'
    | 'applied' | 'interviewing' | 'rejected' | 'offer' | 'ignored';

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
}

function ScoreBadge({ score }: { score: number }) {
    const cls = score >= 75 ? 'score-high' : score >= 50 ? 'score-mid' : 'score-low';
    return (
        <span className={clsx('text-xs font-mono font-bold px-2 py-0.5 rounded-full', cls)}>
            {Math.round(score)}
        </span>
    );
}

const PLATFORM_LABELS: Record<string, string> = {
    linkedin: 'LinkedIn', indeed: 'Indeed', naukri: 'Naukri',
    instahyre: 'InstaHyre', manual: 'Manual',
    company_careers: '🏢 Direct',
};

function PlatformBadge({ platform }: { platform: string }) {
    return (
        <span className={clsx('text-xs font-semibold px-2 py-0.5 rounded-full', `badge-${platform}`)}>
            {PLATFORM_LABELS[platform] || platform}
        </span>
    );
}

interface JobCardProps {
    job: Job;
    onStatusChange: (id: string, status: string) => void;
    onGenerate: (id: string) => void;
    generating?: boolean;
}

const STATUS_OPTIONS = ['discovered', 'scored', 'tailored', 'applied', 'interviewing', 'rejected', 'offer', 'ignored'];

export function JobCard({ job, onStatusChange, onGenerate, generating }: JobCardProps) {
    return (
        <div className="job-card bg-card rounded-xl p-3.5 space-y-2.5 animate-fade-in-up border border-border shadow-card">
            {/* Header */}
            <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                    <p className="font-display font-semibold text-sm text-txt-primary leading-tight truncate">
                        {job.title}
                    </p>
                    <p className="text-xs text-txt-secondary mt-0.5 truncate">{job.company}</p>
                </div>
                <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                    <ScoreBadge score={job.relevance_score} />
                    <PlatformBadge platform={job.platform} />
                </div>
            </div>

            {/* Meta */}
            <div className="flex items-center gap-1.5 flex-wrap">
                {job.location && (
                    <span className="flex items-center gap-1 text-xs text-txt-muted">
                        <MapPin className="w-3 h-3" />{job.location}
                    </span>
                )}
                {job.seniority_level && (
                    <span className="text-xs bg-black/5 border border-border px-1.5 py-0.5 rounded-full text-txt-secondary capitalize">
                        {job.seniority_level}
                    </span>
                )}
                {job.easy_apply && (
                    <span className="text-xs bg-emerald/20 text-emerald border border-emerald/30 px-1.5 py-0.5 rounded-full">
                        Easy Apply
                    </span>
                )}
            </div>

            {/* Fit reason */}
            {job.fit_reason && (
                <p className="text-xs text-txt-secondary italic leading-relaxed line-clamp-2 border-l-2 border-accent pl-2.5">
                    {job.fit_reason}
                </p>
            )}

            {/* Actions */}
            <div className="flex items-center gap-1.5 pt-1 border-t border-border flex-wrap">
                <a
                    href={job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs text-accent hover:text-accent-2 transition-colors"
                >
                    <ExternalLink className="w-3 h-3" /> View
                </a>
                <button
                    onClick={() => onGenerate(job.id)}
                    disabled={generating}
                    className={clsx(
                        'flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border transition-all',
                        generating
                            ? 'border-gold/30 text-gold/40 cursor-not-allowed'
                            : 'border-gold/50 text-gold hover:bg-gold/10 hover:border-gold'
                    )}
                >
                    <Sparkles className="w-3 h-3" />
                    {generating ? 'Working…' : 'AI Resume'}
                </button>
                <Link
                    href={`/outreach?job=${job.id}`}
                    className="flex items-center gap-0.5 text-xs text-txt-muted hover:text-txt-primary transition-colors ml-auto"
                >
                    Outreach <ChevronRight className="w-3 h-3" />
                </Link>
            </div>

            {/* Status changer */}
            <select
                value={job.status}
                onChange={(e) => onStatusChange(job.id, e.target.value)}
                className="input-field w-full text-xs rounded-lg px-2.5 py-1.5 cursor-pointer"
            >
                {STATUS_OPTIONS.map(s => (
                    <option key={s} value={s} className="bg-card text-txt-primary">
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                    </option>
                ))}
            </select>
        </div>
    );
}

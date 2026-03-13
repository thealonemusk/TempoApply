'use client';

import Link from 'next/link';
import { ExternalLink, Sparkles, ChevronRight, MapPin } from 'lucide-react';
import clsx from 'clsx';
import { Job, JobStatus } from './JobCard';

export function ScoreBadge({ score }: { score: number }) {
    const cls = score >= 75 ? 'bg-accent/10 text-accent border border-accent/20' : 
                score >= 50 ? 'bg-gold/10 text-gold border border-gold/20' : 
                'bg-emerald/10 text-emerald border border-emerald/20';
    return (
        <span className={clsx('text-xs font-mono font-bold px-2 py-0.5 rounded-full inline-block text-center min-w-[32px]', cls)}>
            {Math.round(score)}
        </span>
    );
}

const PLATFORM_LABELS: Record<string, string> = {
    linkedin: 'LinkedIn', indeed: 'Indeed', naukri: 'Naukri',
    instahyre: 'InstaHyre', manual: 'Manual',
};

export function PlatformBadge({ platform }: { platform: string }) {
    return (
        <span className={clsx('text-xs font-semibold px-2 py-0.5 rounded-md border border-border bg-card')}>
            {PLATFORM_LABELS[platform] || platform}
        </span>
    );
}

interface JobTableRowProps {
    job: Job;
    onStatusChange: (id: string, status: string) => void;
    onGenerate: (id: string) => void;
    generating?: boolean;
}

const STATUS_OPTIONS = ['discovered', 'scored', 'tailored', 'applied', 'interviewing', 'rejected', 'offer', 'ignored'];

export function JobTableRow({ job, onStatusChange, onGenerate, generating }: JobTableRowProps) {
    return (
        <tr className="hover:bg-black/5 transition-colors border-b border-border group">
            {/* Status */}
            <td className="p-3">
                <select
                    value={job.status}
                    onChange={(e) => onStatusChange(job.id, e.target.value)}
                    className="text-xs bg-transparent font-medium cursor-pointer text-txt-secondary hover:text-txt-primary focus:outline-none"
                    style={{ WebkitAppearance: 'none', appearance: 'none' }}
                >
                    {STATUS_OPTIONS.map(s => (
                        <option key={s} value={s} className="bg-card text-txt-primary">
                            {s.charAt(0).toUpperCase() + s.slice(1)}
                        </option>
                    ))}
                </select>
            </td>

            {/* Title / Company */}
            <td className="p-3">
                <div className="flex flex-col">
                    <span className="font-display font-semibold text-sm text-txt-primary">
                        {job.title}
                    </span>
                    <span className="text-xs text-txt-muted">{job.company}</span>
                </div>
            </td>

            {/* Score */}
            <td className="p-3 text-center">
                <ScoreBadge score={job.relevance_score} />
            </td>

            {/* Platform */}
            <td className="p-3">
                <PlatformBadge platform={job.platform} />
            </td>

            {/* Date */}
            <td className="p-3 text-xs text-txt-muted whitespace-nowrap">
                {job.discovered_at 
                    ? new Date(job.discovered_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) 
                    : 'Unknown Time'}
            </td>

            {/* Actions */}
            <td className="p-3 text-right">
                <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 text-txt-muted hover:text-accent transition-colors rounded-md hover:bg-black/5"
                        title="View Job Post"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                    {/* Hiding tailoring/outreach for now as per user request */}
                    {/* 
                    <button
                        onClick={() => onGenerate(job.id)}
                        disabled={generating}
                        title="Generate Tailored Resume"
                        className={clsx(
                            'p-1.5 rounded-md transition-colors',
                            generating
                                ? 'text-gold/40 cursor-not-allowed'
                                : 'text-gold hover:bg-gold/10'
                        )}
                    >
                        <Sparkles className="w-3.5 h-3.5" />
                    </button>
                    <Link
                        href={`/outreach?job=${job.id}`}
                        className="p-1.5 text-txt-muted hover:text-txt-primary transition-colors rounded-md hover:bg-black/5"
                        title="Outreach"
                    >
                        <ChevronRight className="w-3.5 h-3.5" />
                    </Link> 
                    */}
                </div>
            </td>
        </tr>
    );
}

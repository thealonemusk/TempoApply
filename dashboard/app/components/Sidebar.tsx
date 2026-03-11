'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
    LayoutDashboard, FileText, Mail, BarChart2,
    Settings, Zap, RefreshCw, Sparkles
} from 'lucide-react';
import { useState } from 'react';
import clsx from 'clsx';

const NAV_ITEMS = [
    { href: '/', icon: LayoutDashboard, label: 'Pipeline' },
    { href: '/outreach', icon: Mail, label: 'Outreach' },
    { href: '/resume', icon: FileText, label: 'Resume' },
    { href: '/analytics', icon: BarChart2, label: 'Analytics' },
    { href: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
    const path = usePathname();
    const [scanning, setScanning] = useState(false);
    const [scanStatus, setScanStatus] = useState<string | null>(null);
    const [scanOk, setScanOk] = useState(true);

    const handleScan = async () => {
        setScanning(true);
        setScanStatus(null);
        try {
            const res = await fetch('http://localhost:8000/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ platforms: ['linkedin', 'indeed', 'naukri', 'instahyre'], max_jobs_per_platform: 20, headless: true }),
            });
            const data = await res.json();
            setScanOk(true);
            setScanStatus(data.message || 'Scan started');
        } catch {
            setScanOk(false);
            setScanStatus('API offline');
        }
        setScanning(false);
        setTimeout(() => setScanStatus(null), 5000);
    };

    return (
        <aside className="w-60 min-h-screen flex flex-col border-r border-border bg-card">

            {/* Logo */}
            <div className="px-5 py-6 border-b border-border">
                <div className="flex items-center gap-2.5 mb-0.5">
                    <div className="w-7 h-7 rounded-sm bg-accent flex items-center justify-center flex-shrink-0">
                        <Sparkles className="w-4 h-4 text-white" />
                    </div>
                    <span className="font-display font-bold text-lg text-txt-primary tracking-tight">
                        TempoApply
                    </span>
                </div>
                <p className="text-xs text-txt-muted font-sans mt-1 ml-9">AI Job Agent</p>
            </div>

            {/* Nav */}
            <nav className="flex-1 p-3 space-y-0.5 mt-1">
                {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
                    const active = path === href;
                    return (
                        <Link
                            key={href}
                            href={href}
                            className={clsx(
                                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
                                active
                                    ? 'bg-accent/10 border border-accent/20 text-accent font-semibold'
                                    : 'text-txt-secondary hover:text-txt-primary hover:bg-black/5'
                            )}
                        >
                            <Icon className={clsx('w-4 h-4 flex-shrink-0', active ? 'text-accent' : 'text-txt-muted')} />
                            <span>{label}</span>
                        </Link>
                    );
                })}
            </nav>

            {/* Scan CTA */}
            <div className="p-4 border-t border-border space-y-2">
                <button
                    onClick={handleScan}
                    disabled={scanning}
                    className={clsx(
                        'w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all duration-200',
                        scanning
                            ? 'bg-accent/20 text-accent cursor-not-allowed'
                            : 'bg-accent hover:bg-accent-2 text-white shadow-sm cursor-pointer'
                    )}
                >
                    {scanning
                        ? <RefreshCw className="w-4 h-4 animate-spin" />
                        : <Zap className="w-4 h-4" />}
                    {scanning ? 'Scanning…' : 'Run Scan'}
                </button>
                {scanStatus && (
                    <p className={clsx(
                        'text-xs text-center animate-fade-in',
                        scanOk ? 'text-emerald' : 'text-danger'
                    )}>
                        {scanStatus}
                    </p>
                )}
                <p className="text-xs text-txt-muted text-center">Scans all platforms</p>
            </div>
        </aside>
    );
}

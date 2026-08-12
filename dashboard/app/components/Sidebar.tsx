'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
    Newspaper, LayoutDashboard, FileText,
    Mail, BarChart2, Settings, Zap, RefreshCw
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

    const handleScan = async () => {
        setScanning(true);
        setScanStatus('Scanning…');
        try {
            const res = await fetch('http://localhost:8000/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ platforms: ['linkedin', 'indeed', 'naukri', 'instahyre'], max_jobs_per_platform: 20, headless: true }),
            });
            const data = await res.json();
            setScanStatus(data.message || 'Scan started');
        } catch {
            setScanStatus('API offline');
        }
        setScanning(false);
        setTimeout(() => setScanStatus(null), 4000);
    };

    return (
        <aside className="w-64 min-h-screen bg-ink text-newsprint flex flex-col border-r-4 border-accent-gold">
            {/* Masthead */}
            <div className="p-6 border-b-2 border-accent-gold">
                <div className="flex items-center gap-2 mb-1">
                    <Newspaper className="w-6 h-6 text-accent-gold-light" />
                    <span className="font-serif font-black text-xl tracking-tight text-newsprint">
                        TempoApply
                    </span>
                </div>
                <p className="text-xs text-newsprint/50 font-sans uppercase tracking-widest">
                    AI Job Agent
                </p>
                <div className="mt-3 h-px bg-gradient-to-r from-transparent via-accent-gold to-transparent" />
            </div>

            {/* Nav */}
            <nav className="flex-1 p-4 space-y-1">
                {NAV_ITEMS.map(({ href, icon: Icon, label }) => (
                    <Link
                        key={href}
                        href={href}
                        className={clsx(
                            'flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-all duration-150',
                            path === href
                                ? 'bg-accent-gold text-ink shadow-newspaper font-semibold'
                                : 'text-newsprint/70 hover:bg-ink-light hover:text-newsprint'
                        )}
                    >
                        <Icon className="w-4 h-4 flex-shrink-0" />
                        <span className="font-sans">{label}</span>
                    </Link>
                ))}
            </nav>

            {/* Scan Button */}
            <div className="p-4 border-t border-newsprint/10">
                <button
                    onClick={handleScan}
                    disabled={scanning}
                    className={clsx(
                        'w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded border-2 text-sm font-semibold transition-all duration-200',
                        scanning
                            ? 'border-accent-gold/50 text-accent-gold/50 cursor-not-allowed'
                            : 'border-accent-gold text-accent-gold hover:bg-accent-gold hover:text-ink cursor-pointer'
                    )}
                >
                    {scanning
                        ? <RefreshCw className="w-4 h-4 animate-spin" />
                        : <Zap className="w-4 h-4" />}
                    {scanning ? 'Scanning…' : 'Run Scan'}
                </button>
                {scanStatus && (
                    <p className="mt-2 text-xs text-center text-accent-gold/70 animate-fade-in-up">
                        {scanStatus}
                    </p>
                )}
                <p className="mt-2 text-xs text-newsprint/30 text-center font-sans">
                    Scans all platforms
                </p>
            </div>
        </aside>
    );
}

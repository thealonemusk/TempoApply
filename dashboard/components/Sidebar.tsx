'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTheme } from 'next-themes';
import {
  Activity,
  LayoutDashboard,
  ListChecks,
  Moon,
  Settings,
  Sun,
  WifiOff,
} from 'lucide-react';
import clsx from 'clsx';
import { useEffect, useState } from 'react';
import { useRun } from '@/lib/hooks';

const NAV = [
  { href: '/', icon: LayoutDashboard, label: 'Overview' },
  { href: '/jobs', icon: ListChecks, label: 'Jobs' },
  { href: '/runs', icon: Activity, label: 'Runs' },
  { href: '/settings', icon: Settings, label: 'Settings' },
];

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const { run: applyRun, connected } = useRun('apply');
  const { run: scanRun } = useRun('scan');

  useEffect(() => setMounted(true), []);

  const isDark = mounted && (resolvedTheme ?? theme) === 'dark';
  const activeRun = applyRun.running ? applyRun : scanRun.running ? scanRun : null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-[var(--topbar-h)] shrink-0 items-center gap-2.5 px-4">
        <span className="grid h-7 w-7 place-items-center rounded-md bg-[var(--accent)] text-[13px] font-bold text-[var(--on-accent)]">
          T
        </span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold tracking-[-0.01em] text-[var(--ink)]">
            TempoApply
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-2 py-2">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = href === '/' ? path === '/' : path.startsWith(href);
          const badge =
            href === '/runs' && activeRun
              ? `${activeRun.totals.done}/${activeRun.totals.total || '·'}`
              : null;
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              className={clsx(
                'flex items-center gap-2.5 rounded-[var(--radius)] px-2.5 py-2 text-[13px] font-medium transition-colors',
                active
                  ? 'bg-[var(--surface-hover)] text-[var(--ink)]'
                  : 'text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 truncate">{label}</span>
              {badge && (
                <span className="mono shrink-0 rounded bg-[var(--accent-soft)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--accent)]">
                  {badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-1 border-t border-[var(--line)] p-2">
        {!connected && (
          <p className="flex items-center gap-2 px-2.5 py-1.5 text-[11px] text-[var(--warn)]">
            <WifiOff className="h-3.5 w-3.5 shrink-0" />
            Backend offline
          </p>
        )}
        <button
          type="button"
          onClick={() => setTheme(isDark ? 'light' : 'dark')}
          className="flex w-full items-center gap-2.5 rounded-[var(--radius)] px-2.5 py-2 text-[13px] font-medium text-[var(--ink-muted)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
        >
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {mounted ? (isDark ? 'Light mode' : 'Dark mode') : 'Theme'}
        </button>
      </div>
    </div>
  );
}

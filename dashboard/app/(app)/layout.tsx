'use client';

import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { SidebarNav } from '@/components/Sidebar';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Desktop rail */}
      <aside className="sticky top-0 hidden h-screen w-[var(--sidebar-w)] shrink-0 border-r border-[var(--line)] bg-[var(--surface)] lg:block">
        <SidebarNav />
      </aside>

      {/* Mobile drawer */}
      {navOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/45" onClick={() => setNavOpen(false)} />
          <aside className="anim-fade-up absolute inset-y-0 left-0 w-[var(--sidebar-w)] border-r border-[var(--line)] bg-[var(--surface)]">
            <SidebarNav onNavigate={() => setNavOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <div className="glass sticky top-0 z-30 flex h-[var(--topbar-h)] items-center gap-3 border-b border-[var(--line)] px-4 lg:hidden">
          <button
            type="button"
            onClick={() => setNavOpen((o) => !o)}
            aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
            className="grid h-8 w-8 place-items-center rounded-md text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
          >
            {navOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
          <span className="text-[13px] font-semibold tracking-[-0.01em]">TempoApply</span>
        </div>

        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}

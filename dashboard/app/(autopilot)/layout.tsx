import Link from 'next/link';
import { ArrowLeft, Zap } from 'lucide-react';

/**
 * Shell for the autopilot section.
 *
 * A separate route group with its own chrome — it deliberately does not render
 * the dashboard Sidebar, so this section can change shape without touching the
 * Jobs / Analytics / Settings pages at all. The only shared code is the root
 * layout (html, body, theme) and the read-only UI primitives.
 */
export default function AutopilotLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--bg)]">
      <header className="glass sticky top-0 z-20 border-b border-[var(--border)]">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-8 py-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
          >
            <ArrowLeft className="h-4 w-4" />
            Dashboard
          </Link>
          <div className="h-5 w-px bg-[var(--border)]" />
          <div className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-[var(--accent)]">
              <Zap className="h-4 w-4 text-white" />
            </span>
            <div>
              <h1 className="text-base font-semibold tracking-tight text-[var(--text-primary)]">
                Autopilot
              </h1>
              <p className="text-xs text-[var(--text-muted)]">
                Select, tailor and fill — you approve every submission
              </p>
            </div>
          </div>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

'use client';

import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { AlertTriangle, Check, Info, X } from 'lucide-react';
import clsx from 'clsx';

type Tone = 'success' | 'error' | 'info';

interface Toast {
  id: number;
  tone: Tone;
  title: string;
  detail?: string;
}

interface ToastApi {
  success: (title: string, detail?: string) => void;
  error: (title: string, detail?: string) => void;
  info: (title: string, detail?: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TONES: Record<Tone, { icon: typeof Check; className: string }> = {
  success: { icon: Check, className: 'text-[var(--ok)] bg-[var(--ok-soft)]' },
  error: { icon: AlertTriangle, className: 'text-[var(--danger)] bg-[var(--danger-soft)]' },
  info: { icon: Info, className: 'text-[var(--info)] bg-[var(--info-soft)]' },
};

/** Replaces alert()/confirm() feedback with non-blocking, dismissible toasts. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (tone: Tone, title: string, detail?: string) => {
      const id = Date.now() + Math.random();
      setToasts((prev) => [...prev.slice(-3), { id, tone, title, detail }]);
      // Errors stay longer — they usually carry something to read.
      setTimeout(() => dismiss(id), tone === 'error' ? 8000 : 4000);
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (title, detail) => push('success', title, detail),
      error: (title, detail) => push('error', title, detail),
      info: (title, detail) => push('info', title, detail),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2"
      >
        {toasts.map((t) => {
          const { icon: Icon, className } = TONES[t.tone];
          return (
            <div
              key={t.id}
              className="anim-fade-up pointer-events-auto flex items-start gap-3 rounded-[var(--radius)] border border-[var(--line)] bg-[var(--surface-raised)] p-3 shadow-[var(--shadow-lg)]"
            >
              <span className={clsx('mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md', className)}>
                <Icon className="h-3.5 w-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium leading-snug text-[var(--ink)]">{t.title}</p>
                {t.detail && (
                  <p className="mt-0.5 break-words text-xs leading-snug text-[var(--ink-muted)]">
                    {t.detail}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss"
                className="shrink-0 rounded p-1 text-[var(--ink-subtle)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx;
}

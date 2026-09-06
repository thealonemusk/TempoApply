'use client';

import clsx from 'clsx';
import { Loader2, X } from 'lucide-react';
import {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
  useEffect,
} from 'react';

// ── Button ───────────────────────────────────────────────────────────────────

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: 'xs' | 'sm' | 'md';
  loading?: boolean;
}

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-[var(--accent)] text-[var(--on-accent)] hover:bg-[var(--accent-hover)] shadow-[var(--shadow-sm)]',
  secondary:
    'border border-[var(--line)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] hover:border-[var(--line-strong)]',
  ghost: 'text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]',
  danger:
    'border border-transparent bg-[var(--danger-soft)] text-[var(--danger)] hover:border-[var(--danger)]',
};

const SIZES = {
  xs: 'h-7 gap-1.5 px-2 text-xs',
  sm: 'h-8 gap-1.5 px-2.5 text-[13px]',
  md: 'h-9 gap-2 px-3.5 text-[13px]',
};

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={clsx(
        'inline-flex shrink-0 items-center justify-center rounded-[var(--radius)] font-medium transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-45',
        SIZES[size],
        VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
      {children}
    </button>
  );
}

export function IconButton({
  label,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      className={clsx(
        'inline-grid h-7 w-7 place-items-center rounded-md text-[var(--ink-subtle)] transition-colors',
        'hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]',
        'disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

// ── Surfaces ─────────────────────────────────────────────────────────────────

export function Card({
  children,
  className,
  padded = true,
}: {
  children: React.ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section
      className={clsx(
        'rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow-sm)]',
        padded && 'p-5',
        className,
      )}
    >
      {children}
    </section>
  );
}

export function SectionHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-[var(--ink)]">{title}</h2>
        {description && <p className="mt-0.5 text-xs text-[var(--ink-muted)]">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

// ── Form controls ────────────────────────────────────────────────────────────

const FIELD = [
  'w-full rounded-[var(--radius)] border border-[var(--line)] bg-[var(--surface)] px-3 text-[13px]',
  'text-[var(--ink)] placeholder:text-[var(--ink-subtle)] transition-colors',
  'hover:border-[var(--line-strong)]',
  'focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]',
  'disabled:cursor-not-allowed disabled:opacity-60',
].join(' ');

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={clsx(FIELD, 'h-9', className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={clsx(FIELD, 'resize-y py-2 leading-relaxed', className)} {...props} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={clsx(FIELD, 'h-9 cursor-pointer pr-8', className)} {...props}>
      {children}
    </select>
  );
}

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={clsx('block', className)}>
      <span className="mb-1.5 block text-xs font-medium text-[var(--ink-muted)]">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-[var(--ink-subtle)]">{hint}</span>}
    </label>
  );
}

export function Checkbox({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  hint?: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5"
      />
      <span className="min-w-0">
        <span className="block text-[13px] text-[var(--ink)]">{label}</span>
        {hint && <span className="block text-[11px] text-[var(--ink-subtle)]">{hint}</span>}
      </span>
    </label>
  );
}

// ── Feedback ─────────────────────────────────────────────────────────────────

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      {Icon && (
        <span className="grid h-10 w-10 place-items-center rounded-full bg-[var(--surface-sunken)] text-[var(--ink-subtle)]">
          <Icon className="h-5 w-5" />
        </span>
      )}
      <div>
        <p className="text-[13px] font-medium text-[var(--ink)]">{title}</p>
        {description && (
          <p className="mx-auto mt-1 max-w-sm text-xs text-[var(--ink-muted)]">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <p className="text-[13px] font-medium text-[var(--danger)]">Something went wrong</p>
      <p className="max-w-md text-xs text-[var(--ink-muted)]">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('anim-pulse rounded bg-[var(--surface-sunken)]', className)} />;
}

// ── Modal ────────────────────────────────────────────────────────────────────

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  width = 'max-w-lg',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/45 p-0 sm:items-center sm:p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={clsx(
          'anim-fade-up flex max-h-[92vh] w-full flex-col rounded-t-[var(--radius-lg)] border border-[var(--line)]',
          'bg-[var(--surface-raised)] shadow-[var(--shadow-lg)] sm:rounded-[var(--radius-lg)]',
          width,
        )}
      >
        <header className="flex items-start justify-between gap-4 border-b border-[var(--line)] px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-[var(--ink)]">{title}</h2>
            {description && <p className="mt-0.5 text-xs text-[var(--ink-muted)]">{description}</p>}
          </div>
          <IconButton label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </IconButton>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <footer className="flex justify-end gap-2 border-t border-[var(--line)] px-5 py-3">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}

/** Confirmation dialog — replaces window.confirm for destructive actions. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      description={description}
      width="max-w-md"
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={destructive ? 'danger' : 'primary'}
            size="sm"
            loading={busy}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </>
      }
    />
  );
}

'use client';

import clsx from 'clsx';

/** Sticky page header. `meta` holds small dot-separated counters. */
export function PageHeader({
  title,
  meta,
  actions,
  className,
}: {
  title: string;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={clsx(
        'glass sticky top-0 z-20 border-b border-[var(--line)] px-4 py-3.5 sm:px-6 lg:top-0',
        className,
      )}
    >
      <div className="mx-auto flex max-w-[80rem] flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-[-0.015em] text-[var(--ink)]">{title}</h1>
          {meta && <div className="mt-0.5 text-xs text-[var(--ink-muted)]">{meta}</div>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}

export function PageBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx('px-4 py-5 sm:px-6', className)}>
      <div className="mx-auto max-w-[80rem]">{children}</div>
    </div>
  );
}

/** Dot-separated inline counters for the header meta line. */
export function MetaList({ items }: { items: (string | null | false | undefined)[] }) {
  const parts = items.filter(Boolean) as string[];
  return (
    <span className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
      {parts.map((part, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span aria-hidden className="text-[var(--ink-subtle)]">·</span>}
          {part}
        </span>
      ))}
    </span>
  );
}

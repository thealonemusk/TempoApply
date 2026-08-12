import clsx from 'clsx';

export function Card({
  children,
  className,
  padding = true,
}: {
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
}) {
  return (
    <div
      className={clsx(
        'rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-sm',
        padding && 'p-6',
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-semibold tracking-tight text-[var(--text-primary)]">{children}</h2>;
}

export function CardDescription({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-sm text-[var(--text-muted)]">{children}</p>;
}

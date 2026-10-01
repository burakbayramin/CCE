import type { ReactNode } from 'react';

/* Presentational primitives only. No data fetching, no client state — every
   one of these is safe to render from a server component. */

export function Page({
  children,
  width = 'default',
}: {
  children: ReactNode;
  width?: 'narrow' | 'default' | 'wide';
}) {
  const max = { narrow: 'max-w-2xl', default: 'max-w-3xl', wide: 'max-w-5xl' }[width];
  return <main id="main" className={`mx-auto ${max} px-6 py-10 sm:py-14`}>{children}</main>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  meta,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8">
      {eyebrow && (
        <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
          {eyebrow}
        </div>
      )}
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <h1 className="font-display text-3xl font-semibold leading-tight sm:text-4xl">
          {title}
        </h1>
        {actions && <div className="cce-no-print flex flex-wrap items-center gap-2.5">{actions}</div>}
      </div>
      {description && (
        <p className="mt-3 max-w-2xl text-[0.9375rem] leading-relaxed text-ink-600">{description}</p>
      )}
      {meta && <div className="mt-4">{meta}</div>}
    </header>
  );
}

export function Card({
  children,
  className = '',
  as: Tag = 'section',
}: {
  children: ReactNode;
  className?: string;
  as?: 'section' | 'div' | 'article' | 'aside';
}) {
  return <Tag className={`cce-card ${className}`}>{children}</Tag>;
}

export function CardHeader({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
      <div>
        <h2 className="font-display text-lg font-semibold text-ink-900">{title}</h2>
        {description && <p className="mt-1 text-sm text-ink-600">{description}</p>}
      </div>
      {actions && <div className="cce-no-print flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

const noticeTone = {
  info: 'border-info-100 bg-info-50 text-ink-800',
  success: 'border-success-100 bg-success-50 text-ink-800',
  warning: 'border-amber-soft bg-clay-50 text-ink-800',
  danger: 'border-danger-100 bg-danger-50 text-ink-800',
  neutral: 'border-line bg-paper-sunk text-ink-700',
} as const;

const noticeAccent = {
  info: 'bg-info-700',
  success: 'bg-success-700',
  warning: 'bg-clay-700',
  danger: 'bg-danger-700',
  neutral: 'bg-ink-400',
} as const;

export function Notice({
  tone = 'neutral',
  title,
  children,
  role = 'note',
}: {
  tone?: keyof typeof noticeTone;
  title?: ReactNode;
  children?: ReactNode;
  /** 'note' is decorative prose; use 'alert' for failures and 'status' for progress. */
  role?: 'note' | 'alert' | 'status';
}) {
  return (
    <div
      {...(role === 'note' ? {} : { role })}
      className={`flex gap-3 rounded-lg border px-4 py-3 text-sm leading-relaxed ${noticeTone[tone]}`}
    >
      <span aria-hidden className={`mt-1.5 w-0.5 flex-none rounded-full ${noticeAccent[tone]}`} />
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? 'mt-1' : undefined}>{children}</div>}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  children,
}: {
  title: string;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="cce-card flex flex-col items-start gap-2 border-dashed px-6 py-10">
      <p className="font-display text-lg font-semibold text-ink-800">{title}</p>
      {description && <p className="max-w-md text-sm leading-relaxed text-ink-600">{description}</p>}
      {children && <div className="cce-no-print mt-2">{children}</div>}
    </div>
  );
}

/**
 * Label + control + hint + error, wired with aria-describedby so assistive
 * technology announces the constraint text and the error together. The
 * control must be rendered as `children` with the matching `id` and
 * `aria-describedby`; the previous UI reported errors as an unlinked banner
 * that a screen reader could not attach to any field.
 */
export function Field({
  id,
  label,
  hint,
  error,
  counter,
  children,
  className = '',
}: {
  id: string;
  label: string;
  hint?: ReactNode;
  error?: string;
  counter?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-semibold text-ink-800">
          {label}
        </label>
        {counter && <span className="font-mono text-xs text-ink-500">{counter}</span>}
      </div>
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-xs leading-relaxed text-ink-500">
          {hint}
        </p>
      )}
      <div className="mt-1.5">{children}</div>
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-xs font-medium text-danger-700">
          {error}
        </p>
      )}
    </div>
  );
}

export function describedBy(id: string, hint: boolean, error: boolean) {
  return [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
    .filter(Boolean)
    .join(' ') || undefined;
}

export function DefinitionRow({ term, children }: { term: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 py-2.5">
      <dt className="text-sm text-ink-600">{term}</dt>
      <dd className="min-w-0 text-right font-mono text-sm text-ink-800">{children}</dd>
    </div>
  );
}

export function Mono({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`font-mono text-xs break-all text-ink-600 ${className}`}>{children}</span>;
}

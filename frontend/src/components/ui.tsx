import type { ReactNode } from 'react'

/** Sentiment badge with text label + glyph (never color alone). */
export function SentimentBadge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="text-xs text-slate-400">Not analyzed</span>
  const map: Record<string, { cls: string; glyph: string; label: string }> = {
    positive: { cls: 'bg-emerald-50 text-emerald-800 border-emerald-200', glyph: '▲', label: 'Positive' },
    negative: { cls: 'bg-rose-50 text-rose-800 border-rose-200', glyph: '▼', label: 'Negative' },
    neutral: { cls: 'bg-slate-100 text-slate-700 border-slate-200', glyph: '■', label: 'Neutral' },
  }
  const m = map[value] ?? { cls: 'bg-slate-100 text-slate-600 border-slate-200', glyph: '?', label: value }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${m.cls}`}>
      <span aria-hidden="true">{m.glyph}</span> {m.label}
    </span>
  )
}

/** Priority badge: shape + label, not color alone. */
export function PriorityBadge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="text-xs text-slate-400">—</span>
  const map: Record<string, { cls: string; glyph: string }> = {
    Critical: { cls: 'bg-rose-100 text-rose-900 border-rose-300', glyph: '●●●' },
    High: { cls: 'bg-orange-50 text-orange-900 border-orange-300', glyph: '●●' },
    Medium: { cls: 'bg-amber-50 text-amber-900 border-amber-300', glyph: '●' },
    Low: { cls: 'bg-sky-50 text-sky-900 border-sky-300', glyph: '○' },
  }
  const m = map[value] ?? { cls: 'bg-slate-100 text-slate-600 border-slate-200', glyph: '·' }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${m.cls}`}>
      <span aria-hidden="true" className="text-[9px] tracking-tighter">{m.glyph}</span> {value}
    </span>
  )
}

export function StatusBadge({ value }: { value: string }) {
  const map: Record<string, string> = {
    done: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    pending: 'bg-slate-100 text-slate-600 border-slate-200',
    running: 'bg-sky-50 text-sky-800 border-sky-200',
    failed: 'bg-rose-50 text-rose-800 border-rose-200',
    Open: 'bg-sky-50 text-sky-800 border-sky-200',
    'In Progress': 'bg-indigo-50 text-indigo-800 border-indigo-200',
    Resolved: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    Dismissed: 'bg-slate-100 text-slate-500 border-slate-200',
  }
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${map[value] ?? 'bg-slate-100 text-slate-600 border-slate-200'}`}>
      {value}
    </span>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>{children}</div>
  )
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-navy-950">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-navy-50 text-xl text-navy-600" aria-hidden="true">◍</div>
      <h3 className="text-base font-semibold text-navy-950">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-slate-500">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  disabled,
  type = 'button',
  className = '',
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  disabled?: boolean
  type?: 'button' | 'submit'
  className?: string
}) {
  const styles = {
    primary: 'bg-navy-600 text-white hover:bg-navy-700 disabled:bg-navy-300',
    secondary: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:text-slate-400',
    danger: 'bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300',
    ghost: 'text-navy-700 hover:bg-navy-50 disabled:text-slate-400',
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  )
}

export function Toast({ message, kind }: { message: string | null; kind: 'success' | 'error' }) {
  if (!message) return null
  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-5 right-5 z-50 max-w-md rounded-lg border px-4 py-3 text-sm shadow-lg ${
        kind === 'success' ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-rose-300 bg-rose-50 text-rose-900'
      }`}
    >
      {message}
    </div>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500" role="status">
      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-navy-600" aria-hidden="true" />
      {label ?? 'Loading…'}
    </div>
  )
}

export function trunc(text: string, n = 110) {
  return text.length > n ? text.slice(0, n).trimEnd() + '…' : text
}

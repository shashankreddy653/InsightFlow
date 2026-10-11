import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MessagesSquare,
  Sparkles,
  Lightbulb,
  CircleDot,
  FileText,
  Settings,
  Menu,
  X,
  Waves,
} from 'lucide-react'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/feedback', label: 'Feedback Explorer', icon: MessagesSquare },
  { to: '/insights', label: 'AI Insights', icon: Sparkles },
  { to: '/recommendations', label: 'Recommendations', icon: Lightbulb },
  { to: '/issues', label: 'Issue Tracker', icon: CircleDot },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/settings', label: 'Settings & Integrations', icon: Settings },
]

export default function Layout({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)

  const nav = (
    <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Primary">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={() => setMobileOpen(false)}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-navy-600 text-white shadow-sm'
                : 'text-slate-300 hover:bg-white/10 hover:text-white'
            }`
          }
        >
          <Icon size={18} aria-hidden="true" />
          {label}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col bg-navy-950 lg:flex" aria-label="Sidebar">
        <div className="flex items-center gap-2.5 border-b border-white/10 px-5 py-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-navy-600 text-white" aria-hidden="true">
            <Waves size={20} />
          </span>
          <div>
            <div className="text-sm font-semibold text-white">InsightFlow</div>
            <div className="text-[11px] text-slate-400">Feedback → Decisions</div>
          </div>
        </div>
        {nav}
        <div className="border-t border-white/10 px-5 py-3 text-[11px] text-slate-500">
          Build Battle 2026
        </div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} aria-hidden="true" />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col bg-navy-950 shadow-xl">
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <span className="text-sm font-semibold text-white">InsightFlow</span>
              <button onClick={() => setMobileOpen(false)} aria-label="Close menu" className="text-slate-300 hover:text-white">
                <X size={20} />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur sm:px-6">
          <button
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation menu"
          >
            <Menu size={20} />
          </button>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-navy-950">InsightFlow</div>
            <div className="truncate text-xs text-slate-500">Intelligent Customer Feedback &amp; Decision Platform</div>
          </div>
        </header>
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  )
}

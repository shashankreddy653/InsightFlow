import { useCallback, useEffect, useState } from 'react'
import { Search, Plus, CheckCircle2, RotateCcw, StickyNote } from 'lucide-react'
import { api } from '../lib/api'
import type { Issue, IssueDetail } from '../lib/types'
import { Button, Card, EmptyState, PageHeader, PriorityBadge, Spinner, StatusBadge } from '../components/ui'
import { useToast } from '../lib/toast'

const STATUSES = ['Open', 'In Progress', 'Resolved', 'Dismissed'] as const
const PRIORITIES = ['Critical', 'High', 'Medium', 'Low'] as const

export default function IssueTracker() {
  const toast = useToast()
  const [issues, setIssues] = useState<Issue[] | null>(null)
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [selected, setSelected] = useState<IssueDetail | null>(null)
  const [noteText, setNoteText] = useState('')
  const [planText, setPlanText] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const qs = new URLSearchParams()
      qs.set('saved_only', 'true')
      if (q) qs.set('q', q)
      if (statusFilter) qs.set('status', statusFilter)
      if (priorityFilter) qs.set('priority', priorityFilter)
      const res = await api.get<{ items: Issue[] }>(`/api/issues?${qs.toString()}`)
      setIssues(res.items)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load issues', 'error')
    }
  }, [q, statusFilter, priorityFilter, toast])

  useEffect(() => { void load() }, [load])

  const openDetail = async (id: number) => {
    try {
      const d = await api.get<IssueDetail>(`/api/issues/${id}`)
      setSelected(d)
      setPlanText(d.action_plan ?? '')
      setNoteText('')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load issue', 'error')
    }
  }

  const update = async (id: number, body: Partial<{ status: string; priority: string; action_plan: string; resolution_notes: string }>) => {
    setSaving(true)
    try {
      await api.patch(`/api/issues/${id}`, body)
      await load()
      if (selected?.id === id) await openDetail(id)
      toast('Issue updated — changes are persisted.')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Update failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const addNote = async (id: number) => {
    if (!noteText.trim()) return
    setSaving(true)
    try {
      await api.post(`/api/issues/${id}/notes`, { note_text: noteText.trim() })
      setNoteText('')
      await openDetail(id)
      toast('Note added.')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to add note', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Issue Tracker"
        description="Save important issues, assign owners' plans and notes, and track progress. Everything persists in the database across restarts."
      />

      {/* Filters */}
      <Card className="mb-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="relative">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search saved issues…"
              aria-label="Search saved issues"
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-navy-500 focus:outline-none"
            />
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Filter by status" className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} aria-label="Filter by priority" className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">All priorities</option>
            {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </Card>

      {!issues ? (
        <Spinner label="Loading issues…" />
      ) : issues.length === 0 ? (
        <EmptyState
          title="No saved issues yet"
          body="Open the Recommendations page and press 'Track issue' on an important finding — it will appear here with its evidence and can be managed like a ticket."
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {issues.map((iss) => (
            <Card key={iss.id} className={iss.status === 'Resolved' ? 'opacity-80' : ''}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <button onClick={() => void openDetail(iss.id)} className="text-left text-sm font-semibold text-navy-950 hover:underline">
                    {iss.title}
                  </button>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <PriorityBadge value={iss.priority} />
                    <StatusBadge value={iss.status} />
                    <span>score {iss.priority_score.toFixed(2)}</span>
                    <span>{iss.feedback_count?.toLocaleString()} records</span>
                    <span>updated {iss.updated_at?.slice(0, 10)}</span>
                  </div>
                </div>
                <div className="flex shrink-0 gap-1.5">
                  {iss.status !== 'Resolved' ? (
                    <Button variant="secondary" onClick={() => void update(iss.id, { status: 'Resolved', resolution_notes: iss.resolution_notes ?? 'Resolved from tracker.' })} disabled={saving}>
                      <CheckCircle2 size={14} /> Resolve
                    </Button>
                  ) : (
                    <Button variant="secondary" onClick={() => void update(iss.id, { status: 'Open' })} disabled={saving}>
                      <RotateCcw size={14} /> Reopen
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => void openDetail(iss.id)}>Details</Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Detail drawer */}
      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40" role="dialog" aria-modal="true" aria-label="Issue detail">
          <div className="h-full w-full max-w-2xl overflow-y-auto bg-white shadow-2xl">
            <div className="sticky top-0 border-b border-slate-200 bg-white px-6 py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-navy-950">{selected.title}</h2>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <PriorityBadge value={selected.priority} />
                    <span>System priority: {selected.system_priority}</span>
                    <span>Score {selected.priority_score.toFixed(3)}</span>
                  </div>
                </div>
                <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600" aria-label="Close issue detail">✕</button>
              </div>
            </div>

            <div className="space-y-5 px-6 py-5">
              <p className="text-sm text-slate-600">{selected.description}</p>

              {/* Controls */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="issue-status" className="mb-1 block text-xs font-medium text-slate-500">Status</label>
                  <select id="issue-status" value={selected.status} onChange={(e) => void update(selected.id, { status: e.target.value })} disabled={saving} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
                    {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="issue-prio" className="mb-1 block text-xs font-medium text-slate-500">Priority (override)</label>
                  <select id="issue-prio" value={selected.priority} onChange={(e) => void update(selected.id, { priority: e.target.value })} disabled={saving} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
                    {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
              </div>

              {/* Action plan */}
              <div>
                <label htmlFor="issue-plan" className="mb-1 block text-xs font-medium text-slate-500">Action plan</label>
                <textarea id="issue-plan" rows={3} value={planText} onChange={(e) => setPlanText(e.target.value)} placeholder="What will be done, by whom, by when…" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-navy-500 focus:outline-none" />
                <div className="mt-1.5 flex items-center gap-2">
                  <Button variant="secondary" onClick={() => void update(selected.id, { action_plan: planText })} disabled={saving}>Save plan</Button>
                  {selected.status === 'Resolved' && (
                    <div className="flex-1">
                      <label htmlFor="issue-res" className="sr-only">Resolution notes</label>
                      <input id="issue-res" value={selected.resolution_notes ?? ''} onChange={(e) => void update(selected.id, { resolution_notes: e.target.value })} placeholder="Resolution notes…" className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs" />
                    </div>
                  )}
                </div>
              </div>

              {/* Recommendation */}
              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  AI recommendation {selected.recommendation_source === 'llm' ? '(LLM-generated)' : '(template engine)'}
                </h3>
                <p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm leading-relaxed text-slate-700">{selected.recommendation}</p>
                {selected.success_metric && <p className="mt-1.5 text-xs text-slate-600"><b>Success metric:</b> {selected.success_metric}</p>}
              </div>

              {/* Supporting stats */}
              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Supporting statistics</h3>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Stat label="Records" value={selected.metrics?.record_count ?? 0} />
                  <Stat label="Unique texts" value={selected.metrics?.unique_count ?? 0} />
                  <Stat label="Negative" value={`${Math.round((selected.metrics?.negative_ratio ?? 0) * 100)}%`} />
                  <Stat label="Factors used" value={(selected.factors_used ?? []).join(', ') || '—'} small />
                </div>
              </div>

              {/* Evidence */}
              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Associated feedback records</h3>
                <ul className="max-h-64 space-y-2 overflow-y-auto thin-scroll">
                  {(selected.evidence ?? []).map((ev) => (
                    <li key={ev.feedback_id} className="rounded-lg border border-slate-200 p-2.5">
                      <p className="text-sm text-slate-700">“{ev.review_text}”</p>
                      <div className="mt-1 text-[11px] text-slate-400">
                        {ev.original_category ?? 'no category'} · {ev.sentiment} ({ev.sentiment_score?.toFixed(2)}) · #{ev.feedback_id}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Notes */}
              <div>
                <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <StickyNote size={13} aria-hidden="true" /> Notes
                </h3>
                {(selected.notes ?? []).length === 0 && <p className="text-xs text-slate-400">No notes yet.</p>}
                <ul className="space-y-2">
                  {(selected.notes ?? []).map((n) => (
                    <li key={n.id} className="rounded-lg border border-amber-100 bg-amber-50/60 p-2.5 text-sm text-slate-700">
                      {n.note_text}
                      <div className="mt-1 text-[11px] text-slate-400">{n.created_at?.slice(0, 16).replace('T', ' ')}</div>
                    </li>
                  ))}
                </ul>
                <div className="mt-2 flex gap-2">
                  <label htmlFor="new-note" className="sr-only">New note</label>
                  <input id="new-note" value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="Add a note…" className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-navy-500 focus:outline-none" />
                  <Button onClick={() => void addNote(selected.id)} disabled={saving || !noteText.trim()}><Plus size={14} /> Add</Button>
                </div>
              </div>

              <p className="text-[11px] text-slate-400">
                Created {selected.created_at?.slice(0, 16).replace('T', ' ')} UTC · Updated {selected.updated_at?.slice(0, 16).replace('T', ' ')} UTC
                <br />These are application timestamps for issue-management events, not customer-feedback timestamps.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function Stat({ label, value, small }: { label: string; value: string | number; small?: boolean }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="text-[11px] font-medium text-slate-500">{label}</div>
      <div className={`${small ? 'text-xs' : 'text-base'} font-semibold text-navy-950`}>{value}</div>
    </div>
  )
}

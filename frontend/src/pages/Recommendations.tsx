import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Save, CheckCircle2, Gauge } from 'lucide-react'
import { api } from '../lib/api'
import type { Issue } from '../lib/types'
import { Button, Card, EmptyState, PageHeader, PriorityBadge, SentimentBadge, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

const FACTOR_LABELS: Record<string, string> = {
  frequency: 'Issue frequency',
  negative: 'Negative sentiment ratio',
  severity: 'Estimated severity',
  trend: 'Trend over time',
}

export default function Recommendations() {
  const toast = useToast()
  const [params] = useSearchParams()
  const highlightId = Number(params.get('issue') ?? '0')
  const [issues, setIssues] = useState<Issue[] | null>(null)
  const [filter, setFilter] = useState<'all' | 'high' | 'saved'>('all')
  const [expanded, setExpanded] = useState<number | null>(highlightId || null)
  const [saving, setSaving] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await api.get<Issue[]>('/api/analytics/issues')
      setIssues(data)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load recommendations', 'error')
    }
  }, [toast])

  useEffect(() => { void load() }, [load])
  useEffect(() => { if (highlightId) setExpanded(highlightId) }, [highlightId])

  const visible = useMemo(() => {
    if (!issues) return []
    if (filter === 'high') return issues.filter((i) => i.priority === 'Critical' || i.priority === 'High')
    if (filter === 'saved') return issues.filter((i) => i.saved)
    return issues
  }, [issues, filter])

  const saveIssue = async (id: number) => {
    setSaving(id)
    try {
      await api.post(`/api/issues/${id}/save`)
      toast('Issue saved to the Issue Tracker.')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to save issue', 'error')
    } finally {
      setSaving(null)
    }
  }

  if (!issues) return <Spinner label="Loading recommendations…" />
  if (issues.length === 0) {
    return (
      <>
        <PageHeader title="Intelligent Recommendations" description="Evidence-backed actions for your most important issues." />
        <EmptyState title="No issues identified yet" body="Import feedback and run the analysis to generate recommendations." />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Intelligent Recommendations"
        description="Every recommendation is grounded in actual feedback records. Priority scores are transparent and explainable — open any card to see the exact factors."
        actions={
          <div className="flex rounded-lg border border-slate-300 bg-white p-0.5 text-sm" role="group" aria-label="Filter recommendations">
            {(['all', 'high', 'saved'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-md px-3 py-1.5 font-medium capitalize ${filter === f ? 'bg-navy-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}
              >
                {f === 'high' ? 'Critical & High' : f}
              </button>
            ))}
          </div>
        }
      />

      {visible.length === 0 ? (
        <EmptyState title="Nothing matches this filter" body="Switch the filter to see all identified issues." />
      ) : (
        <div className="space-y-4">
          {visible.map((iss) => {
            const open = expanded === iss.id
            const m = iss.metrics ?? {}
            return (
              <Card key={iss.id} className={iss.priority === 'Critical' ? 'border-rose-200' : ''}>
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-semibold text-navy-950">{iss.title}</h3>
                      <PriorityBadge value={iss.priority} />
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                        <Gauge size={12} aria-hidden="true" /> Score {iss.priority_score.toFixed(2)}
                      </span>
                      {iss.recommendation_source === 'llm' ? (
                        <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-800">LLM-generated</span>
                      ) : (
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-600">Template engine</span>
                      )}
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span>{m.record_count?.toLocaleString()} related records ({m.unique_count} unique texts)</span>
                      <span>{Math.round((m.negative_ratio ?? 0) * 100)}% negative sentiment</span>
                      {m.category_breakdown && (
                        <span>Categories: {Object.entries(m.category_breakdown).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([k, v]) => `${k} (${v})`).join(', ')}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button variant="secondary" onClick={() => setExpanded(open ? null : iss.id)}>
                      {open ? 'Hide details' : 'Evidence & details'}
                    </Button>
                    {iss.saved ? (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">
                        <CheckCircle2 size={15} /> Tracking
                      </span>
                    ) : (
                      <Button onClick={() => void saveIssue(iss.id)} disabled={saving === iss.id}>
                        <Save size={15} /> {saving === iss.id ? 'Saving…' : 'Track issue'}
                      </Button>
                    )}
                  </div>
                </div>

                {open && (
                  <div className="mt-4 grid gap-4 border-t border-slate-100 pt-4 lg:grid-cols-2">
                    {/* Evidence + score */}
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Why this priority</h4>
                      <ScoreBreakdown issue={iss} />
                      <h4 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Recommendation</h4>
                      <p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm leading-relaxed text-slate-700">{iss.recommendation}</p>
                      {iss.success_metric && (
                        <p className="mt-2 text-xs text-slate-600">
                          <span className="font-semibold">Suggested success metric:</span> {iss.success_metric}
                        </p>
                      )}
                      {iss.factors_unavailable?.includes('trend') && (
                        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
                          Trend factor unavailable: the dataset has no timestamps, so its weight was renormalized across
                          the remaining factors instead of being invented.
                        </p>
                      )}
                    </div>
                    {/* Representative feedback */}
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Supporting feedback examples</h4>
                      <EvidenceList issueId={iss.id} representative={m.representative_text} />
                    </div>
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </>
  )
}

function ScoreBreakdown({ issue }: { issue: Issue }) {
  const b = issue.score_breakdown ?? {}
  const components = b.components ?? {}
  const weights = b.weights_used ?? {}
  const rows = Object.entries(components)
  if (rows.length === 0) return null
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="pb-1 font-medium">Factor</th>
            <th className="pb-1 font-medium">Value</th>
            <th className="pb-1 font-medium">Weight used</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-t border-slate-100">
              <td className="py-1.5 text-slate-700">{FACTOR_LABELS[k] ?? k}</td>
              <td className="py-1.5">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-16 overflow-hidden rounded bg-slate-100">
                    <div className="h-full bg-navy-500" style={{ width: `${Math.round(v * 100)}%` }} />
                  </div>
                  <span className="tabular-nums text-slate-600">{v.toFixed(2)}</span>
                </div>
              </td>
              <td className="py-1.5 tabular-nums text-slate-600">{Math.round((weights[k] ?? 0) * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
        Score = Σ(factor × weight) over available factors. Base severity for this topic: {(b.severity_base ?? 0).toFixed(2)}.
        Critical additionally requires severity ≥ 0.70, so frequent mild complaints never auto-escalate.
      </p>
    </div>
  )
}

function EvidenceList({ issueId, representative }: { issueId: number; representative?: string }) {
  const [evidence, setEvidence] = useState<{ feedback_id: number; review_text: string; sentiment: string | null; sentiment_score: number | null }[] | null>(null)
  const toast = useToast()
  useEffect(() => {
    api
      .get<{ evidence: { feedback_id: number; review_text: string; sentiment: string | null; sentiment_score: number | null }[] }>(`/api/issues/${issueId}?limit=6`)
      .then((d) => setEvidence(d.evidence))
      .catch((err) => toast(err instanceof Error ? err.message : 'Failed to load evidence', 'error'))
  }, [issueId, toast])

  if (!evidence) return <Spinner label="Loading evidence…" />
  if (evidence.length === 0) {
    return representative ? (
      <p className="rounded-lg bg-slate-50 p-3 text-sm italic text-slate-600">“{representative}”</p>
    ) : (
      <p className="text-sm text-slate-500">No linked feedback records.</p>
    )
  }
  return (
    <ul className="space-y-2">
      {evidence.map((ev) => (
        <li key={ev.feedback_id} className="rounded-lg border border-slate-200 p-2.5">
          <p className="text-sm text-slate-700">“{ev.review_text}”</p>
          <div className="mt-1.5 flex items-center gap-2 text-[11px] text-slate-400">
            <SentimentBadge value={ev.sentiment} />
            {ev.sentiment_score !== null && <span>score {ev.sentiment_score?.toFixed(2)}</span>}
            <span>record #{ev.feedback_id}</span>
          </div>
        </li>
      ))}
    </ul>
  )
}

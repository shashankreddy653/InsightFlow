import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { Info, FlaskConical, ArrowRight } from 'lucide-react'
import { api } from '../lib/api'
import type { Charts, Issue, Summary } from '../lib/types'
import { Card, EmptyState, PageHeader, PriorityBadge, SentimentBadge, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

type EvalResult = {
  evaluated_at: string
  total: number
  clear_total: number
  ambiguous_total: number
  sentiment_accuracy: number
  topic_accuracy: number
  ambiguous_sentiment_agreement: number
  sample_mismatches: {
    review: string
    expected_sentiment: string
    got_sentiment: string
    expected_topic: string
    got_topic: string
    ambiguous: boolean
  }[]
}

const TOPIC_COLORS = ['#4338ca', '#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe', '#e0e7ff', '#0ea5e9', '#38bdf8']

export default function Insights() {
  const toast = useToast()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [charts, setCharts] = useState<Charts | null>(null)
  const [issues, setIssues] = useState<Issue[]>([])
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null)
  const [evalRunning, setEvalRunning] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [s, c, i] = await Promise.all([
        api.get<Summary>('/api/analytics/summary'),
        api.get<Charts>('/api/analytics/charts'),
        api.get<Issue[]>('/api/analytics/issues'),
      ])
      setSummary(s)
      setCharts(c)
      setIssues(i)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load insights', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => { void load() }, [load])

  const runEval = async () => {
    setEvalRunning(true)
    try {
      const res = await api.post<EvalResult>('/api/integrations/adaption/evaluate')
      setEvalResult(res)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Evaluation failed', 'error')
    } finally {
      setEvalRunning(false)
    }
  }

  if (loading) return <Spinner label="Loading insights…" />
  if (!summary || summary.total_records === 0) {
    return (
      <>
        <PageHeader title="AI Insights" description="Patterns discovered by the analysis pipeline." />
        <EmptyState title="No feedback analyzed yet" body="Import a dataset and run the analysis to see AI-derived insights." action={<Link to="/feedback" className="text-sm font-medium text-navy-600 hover:underline">Go to Feedback Explorer →</Link>} />
      </>
    )
  }

  const topicData = (charts?.topic_distribution ?? []).map((t) => ({ ...t }))
  const groupByTopic = new Map<string, Issue[]>()
  for (const iss of issues) {
    const key = iss.topic ?? 'General Feedback'
    if (!groupByTopic.has(key)) groupByTopic.set(key, [])
    groupByTopic.get(key)!.push(iss)
  }
  const topicEntries = [...groupByTopic.entries()].sort((a, b) => b[1].length - a[1].length)

  return (
    <>
      <PageHeader
        title="AI Insights"
        description="What customers are talking about, how they feel, and which similar complaints were grouped together — all derived from your actual feedback."
      />

      {/* Transparency banner */}
      <Card className="mb-6 border-navy-200 bg-navy-50/60">
        <div className="flex gap-3">
          <Info size={18} className="mt-0.5 shrink-0 text-navy-600" aria-hidden="true" />
          <div className="text-sm leading-relaxed text-slate-700">
            <span className="font-semibold text-navy-950">How these insights are produced.</span>{' '}
            Original dataset values (review text, original category) are shown verbatim and never overwritten.
            Sentiment is computed by VADER with a domain-tuned lexicon; topics are assigned by a transparent keyword lexicon;
            similar reviews are grouped with TF-IDF cosine similarity clustering. Priority scores are rule-based and
            fully explainable. Nothing here claims a proven root cause — the system surfaces recurring complaints and correlations.
          </div>
        </div>
      </Card>

      {/* Topic distribution */}
      <Card className="mb-6">
        <h2 className="mb-1 text-sm font-semibold text-navy-950">Identified topics across all records</h2>
        <p className="mb-3 text-xs text-slate-500">Topic counts are record-level (duplicates included for volume). Grouping into issues below uses unique texts.</p>
        <ResponsiveContainer width="100%" height={Math.max(240, topicData.length * 30)}>
          <BarChart data={topicData} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="topic" width={220} tick={{ fontSize: 10.5 }} />
            <Tooltip formatter={(v) => [Number(v).toLocaleString(), 'Records']} />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              {topicData.map((_, idx) => <Cell key={idx} fill={TOPIC_COLORS[idx % TOPIC_COLORS.length]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* Similarity groups per topic */}
      <div className="mb-6">
        <h2 className="mb-3 text-sm font-semibold text-navy-950">Similarity groups (issue clusters)</h2>
        {issues.length === 0 ? (
          <EmptyState title="No groups yet" body="Run the analysis to cluster similar feedback into issue groups." />
        ) : (
          <div className="space-y-5">
            {topicEntries.slice(0, 6).map(([topic, groupIssues]) => (
              <Card key={topic}>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-navy-950">{topic}</h3>
                  <span className="text-xs text-slate-500">{groupIssues.length} group{groupIssues.length === 1 ? '' : 's'}</span>
                </div>
                <div className="grid gap-2 lg:grid-cols-2">
                  {groupIssues.slice(0, 4).map((iss) => (
                    <div key={iss.id} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <Link to={`/recommendations?issue=${iss.id}`} className="text-sm font-medium text-navy-900 hover:underline">{iss.title}</Link>
                        <PriorityBadge value={iss.priority} />
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {iss.metrics?.record_count?.toLocaleString()} records ({iss.metrics?.unique_count} unique texts) ·{' '}
                        {Math.round((iss.metrics?.negative_ratio ?? 0) * 100)}% negative
                      </div>
                      {iss.metrics?.representative_text && (
                        <p className="mt-2 rounded bg-slate-50 p-2 text-xs italic text-slate-600">“{iss.metrics.representative_text.slice(0, 140)}…”</p>
                      )}
                      <div className="mt-2 flex items-center gap-2 text-xs">
                        <SentimentBadge value={(iss.metrics?.negative_ratio ?? 0) > 0.5 ? 'negative' : (iss.metrics?.negative_ratio ?? 0) < 0.2 ? 'positive' : 'neutral'} />
                        <Link to={`/recommendations?issue=${iss.id}`} className="inline-flex items-center gap-1 font-medium text-navy-600 hover:underline">
                          Evidence & recommendation <ArrowRight size={12} />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Pipeline evaluation */}
      <Card>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-navy-950">
              <FlaskConical size={16} className="text-navy-600" aria-hidden="true" /> Pipeline quality evaluation
            </h2>
            <p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-500">
              The analysis pipeline is scored against a hand-labeled reference subset drawn from this dataset's unique
              review texts. Ambiguous mixed reviews (problem + resolution) are scored separately. This evaluation is
              also the honest baseline for the Adaption workflow on the Settings page.
            </p>
          </div>
          <button
            onClick={() => void runEval()}
            disabled={evalRunning}
            className="shrink-0 rounded-lg bg-navy-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-navy-700 disabled:bg-navy-300"
          >
            {evalRunning ? 'Evaluating…' : 'Run evaluation'}
          </button>
        </div>
        {evalResult && (
          <div className="mt-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <MetricBox label="Sentiment accuracy" value={`${Math.round(evalResult.sentiment_accuracy * 100)}%`} sub={`${evalResult.clear_total} clear items`} />
              <MetricBox label="Topic accuracy" value={`${Math.round(evalResult.topic_accuracy * 100)}%`} sub={`${evalResult.clear_total} clear items`} />
              <MetricBox label="Ambiguous agreement" value={`${Math.round(evalResult.ambiguous_sentiment_agreement * 100)}%`} sub={`${evalResult.ambiguous_total} mixed items`} />
              <MetricBox label="Reference size" value={evalResult.total} sub="hand-labeled examples" />
            </div>
            {evalResult.sample_mismatches.length > 0 && (
              <div className="mt-4">
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Sample mismatches</h4>
                <ul className="space-y-1 text-xs text-slate-600">
                  {evalResult.sample_mismatches.slice(0, 5).map((m, i) => (
                    <li key={i} className="rounded bg-slate-50 p-2">
                      “{m.review}…” → expected <b>{m.expected_sentiment}</b>/<b>{m.expected_topic}</b>, got{' '}
                      <b>{m.got_sentiment}</b>/<b>{m.got_topic}</b>{m.ambiguous && <span className="text-amber-700"> (ambiguous item)</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Card>
    </>
  )
}

function MetricBox({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="text-lg font-semibold text-navy-950">{value}</div>
      {sub && <div className="text-[11px] text-slate-400">{sub}</div>}
    </div>
  )
}

import { useCallback, useEffect, useState } from 'react'
import { FileDown, FileText, FileType, RefreshCw, Copy } from 'lucide-react'
import { api, downloadFile } from '../lib/api'
import type { Charts, ReportMeta, Summary } from '../lib/types'
import { Button, Card, EmptyState, PageHeader, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

type Snapshot = {
  title: string
  generated_at: string
  dataset_summary: Record<string, number>
  sentiment_distribution: Record<string, number>
  category_distribution: Record<string, number>
  topic_distribution: Record<string, number>
  priority_distribution: Record<string, number>
  top_issues: { id: number; title: string; priority: string; priority_score: number; record_count: number; negative_ratio: number; success_metric: string | null }[]
  limitations: string[]
}

export default function Reports() {
  const toast = useToast()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [charts, setCharts] = useState<Charts | null>(null)
  const [history, setHistory] = useState<ReportMeta[]>([])
  const [generating, setGenerating] = useState(false)
  const [lastSnapshot, setLastSnapshot] = useState<Snapshot | null>(null)
  const [lastId, setLastId] = useState<number | null>(null)
  const [sentimentFilter, setSentimentFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [s, c, h] = await Promise.all([
        api.get<Summary>('/api/analytics/summary'),
        api.get<Charts>('/api/analytics/charts'),
        api.get<ReportMeta[]>('/api/reports'),
      ])
      setSummary(s)
      setCharts(c)
      setHistory(h)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load reports', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => { void load() }, [load])

  const generate = async () => {
    setGenerating(true)
    try {
      const filters: Record<string, string> = {}
      if (sentimentFilter) filters.sentiment = sentimentFilter
      if (categoryFilter) filters.category = categoryFilter
      const res = await api.post<{ id: number; snapshot: Snapshot }>('/api/reports/generate', filters)
      setLastSnapshot(res.snapshot)
      setLastId(res.id)
      toast('Report generated. Exports reflect exactly this snapshot.')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Report generation failed', 'error')
    } finally {
      setGenerating(false)
    }
  }

  const copySummary = () => {
    if (!lastSnapshot) return
    const s = lastSnapshot
    const text = [
      s.title,
      `Generated: ${new Date(s.generated_at).toLocaleString()}`,
      '',
      `Total records: ${s.dataset_summary.total_feedback_records?.toLocaleString()}`,
      `Unique texts: ${s.dataset_summary.unique_review_texts?.toLocaleString()}`,
      `Sentiment — positive: ${s.sentiment_distribution.positive ?? 0}, neutral: ${s.sentiment_distribution.neutral ?? 0}, negative: ${s.sentiment_distribution.negative ?? 0}`,
      '',
      'Top issues:',
      ...s.top_issues.slice(0, 5).map((i) => `• ${i.title} [${i.priority}, score ${i.priority_score.toFixed(2)}] — ${i.record_count} records, ${Math.round(i.negative_ratio * 100)}% negative`),
      '',
      'Limitations:',
      ...s.limitations.map((l) => `• ${l}`),
    ].join('\n')
    navigator.clipboard.writeText(text)
      .then(() => toast('Executive summary copied to clipboard.'))
      .catch(() => toast('Could not access clipboard.', 'error'))
  }

  if (loading) return <Spinner label="Loading reports…" />
  if (!summary || summary.total_records === 0) {
    return (
      <>
        <PageHeader title="Reports & Exports" description="Generate business-friendly insight reports from your analyzed data." />
        <EmptyState title="Nothing to report yet" body="Import feedback and run the analysis first, then generate a report here." />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Reports & Exports"
        description="Generate a report snapshot from the current dataset and filters, then export it as PDF or CSV. Every export reflects actual application data."
        actions={<Button onClick={() => void generate()} disabled={generating}><FileText size={15} /> {generating ? 'Generating…' : 'Generate report'}</Button>}
      />

      {/* Filters for the report */}
      <Card className="mb-6">
        <h2 className="mb-3 text-sm font-semibold text-navy-950">Report scope</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor="rep-sent" className="mb-1 block text-xs font-medium text-slate-500">Sentiment filter (optional)</label>
            <select id="rep-sent" value={sentimentFilter} onChange={(e) => setSentimentFilter(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <option value="">All sentiments</option>
              {(charts?.sentiment_distribution ? Object.keys(charts.sentiment_distribution) : []).map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="rep-cat" className="mb-1 block text-xs font-medium text-slate-500">Category filter (optional)</label>
            <select id="rep-cat" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <option value="">All categories</option>
              {(charts?.category_distribution ?? []).map((c) => <option key={c.category} value={c.category}>{c.category}</option>)}
            </select>
          </div>
          <div className="flex items-end">
            <p className="text-xs text-slate-500">The dataset snapshot (records, unique texts, distributions) always covers the full current dataset; filter metadata is stored with the report.</p>
          </div>
        </div>
      </Card>

      {/* Latest snapshot */}
      {lastSnapshot ? (
        <Card className="mb-6 border-navy-200">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-navy-950">{lastSnapshot.title}</h2>
              <p className="text-xs text-slate-500">Generated {new Date(lastSnapshot.generated_at).toLocaleString()} · Report #{lastId}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => lastId && downloadFile(`/api/reports/${lastId}/export/csv`, `insightflow-report-${lastId}.csv`)}>
                <FileDown size={15} /> CSV
              </Button>
              <Button variant="secondary" onClick={() => lastId && downloadFile(`/api/reports/${lastId}/export/pdf`, `insightflow-report-${lastId}.pdf`)}>
                <FileType size={15} /> PDF
              </Button>
              <Button variant="ghost" onClick={copySummary}><Copy size={15} /> Copy summary</Button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Box label="Total records" value={lastSnapshot.dataset_summary.total_feedback_records?.toLocaleString() ?? '—'} />
            <Box label="Unique texts" value={lastSnapshot.dataset_summary.unique_review_texts?.toLocaleString() ?? '—'} />
            <Box label="Positive" value={lastSnapshot.sentiment_distribution.positive ?? 0} />
            <Box label="Negative" value={lastSnapshot.sentiment_distribution.negative ?? 0} />
          </div>
          <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">High-priority issues in this report</h3>
          <ul className="space-y-1.5">
            {lastSnapshot.top_issues.slice(0, 5).map((i) => (
              <li key={i.id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                <span className="font-medium text-navy-950">{i.title}</span>
                <span className="ml-2 text-xs text-slate-500">[{i.priority}, score {i.priority_score.toFixed(2)}] — {i.record_count.toLocaleString()} records, {Math.round(i.negative_ratio * 100)}% negative</span>
              </li>
            ))}
          </ul>
          <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Documented limitations</h3>
          <ul className="list-inside list-disc space-y-1 text-xs text-slate-600">
            {lastSnapshot.limitations.map((l, i) => <li key={i}>{l}</li>)}
          </ul>
        </Card>
      ) : (
        <Card className="mb-6 border-dashed">
          <p className="text-sm text-slate-500">No report generated in this session yet. Press <b>Generate report</b> to create a snapshot — you can then export it as PDF or CSV.</p>
        </Card>
      )}

      {/* Quick exports */}
      <Card className="mb-6">
        <h2 className="mb-1 text-sm font-semibold text-navy-950">Quick data exports</h2>
        <p className="mb-3 text-xs text-slate-500">Direct CSV downloads of current application data.</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => downloadFile('/api/reports/export/feedback.csv', 'feedback-all.csv')}>
            <FileDown size={15} /> All feedback (+ analysis)
          </Button>
          <Button variant="secondary" onClick={() => downloadFile('/api/reports/export/feedback.csv?sentiment=negative', 'feedback-negative.csv')}>
            <FileDown size={15} /> Negative feedback only
          </Button>
          <Button variant="secondary" onClick={() => downloadFile('/api/reports/export/issues.csv', 'issues.csv')}>
            <FileDown size={15} /> Issue list
          </Button>
        </div>
      </Card>

      {/* History */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-navy-950">Report history</h2>
          <Button variant="ghost" onClick={() => void load()}><RefreshCw size={14} /> Refresh</Button>
        </div>
        {history.length === 0 ? (
          <p className="text-sm text-slate-500">No reports generated yet. Generated reports are stored with their metadata and snapshot for later review.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {history.map((r) => (
              <li key={r.id} className="flex items-center justify-between py-2.5">
                <div>
                  <div className="text-sm font-medium text-navy-950">#{r.id} — {r.title}</div>
                  <div className="text-xs text-slate-500">
                    {r.created_at?.slice(0, 16).replace('T', ' ')} UTC · {r.report_type}
                    {Object.keys(r.filters ?? {}).length > 0 && ` · filters: ${Object.entries(r.filters).map(([k, v]) => `${k}=${v}`).join(', ')}`}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" onClick={() => downloadFile(`/api/reports/${r.id}/export/csv`, `report-${r.id}.csv`)}><FileDown size={14} /> CSV</Button>
                  <Button variant="ghost" onClick={() => downloadFile(`/api/reports/${r.id}/export/pdf`, `report-${r.id}.pdf`)}><FileType size={14} /> PDF</Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}

function Box({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="text-[11px] font-medium text-slate-500">{label}</div>
      <div className="text-base font-semibold text-navy-950">{value}</div>
    </div>
  )
}

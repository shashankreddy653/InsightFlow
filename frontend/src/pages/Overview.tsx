import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, Cell,
  PieChart, Pie, Cell as PieCell,
  ResponsiveContainer, Tooltip, XAxis, YAxis, Legend, CartesianGrid,
} from 'recharts'
import {
  Upload, FileText, Play, AlertTriangle, FileBarChart, RefreshCw,
} from 'lucide-react'
import { api } from '../lib/api'
import type { Charts, JobStatus, Issue, Summary } from '../lib/types'
import { Button, Card, EmptyState, PageHeader, PriorityBadge, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

const SENT_COLORS: Record<string, string> = { positive: '#10b981', negative: '#e11d48', neutral: '#94a3b8' }
const PRIORITY_COLORS: Record<string, string> = { Critical: '#e11d48', High: '#f97316', Medium: '#f59e0b', Low: '#0ea5e9' }

function KpiCard({ label, value, hint, accent }: { label: string; value: string | number; hint?: string; accent?: string }) {
  return (
    <Card className="relative overflow-hidden">
      {accent && <span className="absolute left-0 top-0 h-full w-1" style={{ background: accent }} aria-hidden="true" />}
      <div className="pl-2">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
        <div className="mt-1 text-2xl font-semibold text-navy-950">{value}</div>
        {hint && <div className="mt-1 text-xs text-slate-400">{hint}</div>}
      </div>
    </Card>
  )
}

export default function Overview() {
  const toast = useToast()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [charts, setCharts] = useState<Charts | null>(null)
  const [issues, setIssues] = useState<Issue[]>([])
  const [job, setJob] = useState<JobStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const pollRef = useRef<number | null>(null)

  const loadAll = useCallback(async () => {
    try {
      const [s, c, i] = await Promise.all([
        api.get<Summary>('/api/analytics/summary'),
        api.get<Charts>('/api/analytics/charts'),
        api.get<Issue[]>('/api/analytics/issues'),
      ])
      setSummary(s)
      setCharts(c)
      setIssues(i.slice(0, 5))
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load dashboard', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => { void loadAll() }, [loadAll])

  // Poll while an analysis job is running
  useEffect(() => {
    const poll = async () => {
      try {
        const j = await api.get<JobStatus>('/api/analytics/job')
        setJob(j)
        if (j.status === 'running' || j.status === 'pending') {
          pollRef.current = window.setTimeout(poll, 2000)
        } else {
          void loadAll()
        }
      } catch {
        pollRef.current = window.setTimeout(poll, 500)
      }
    }
    pollRef.current = window.setTimeout(poll, 500)
    return () => { if (pollRef.current) window.clearTimeout(pollRef.current) }
  }, [loadAll])

  const runAnalysis = async () => {
    try {
      await api.post('/api/analytics/analyze')
      toast('Analysis queued — progress shown below.')
      const j = await api.get<JobStatus>('/api/analytics/job')
      setJob(j)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to start analysis', 'error')
    }
  }

  if (loading) return <Spinner label="Loading dashboard…" />
  if (!summary) return <EmptyState title="Dashboard unavailable" body="The API did not return data. Check that the backend is running on port 8000." />

  if (summary.total_records === 0) {
    return (
      <>
        <PageHeader title="Overview" description="Welcome to InsightFlow — your feedback-to-decision workspace." />
        <EmptyState
          title="No feedback yet"
          body="Upload the Build Battle CSV (or any feedback CSV) to get started. InsightFlow will import, analyze, group, and prioritize it automatically."
          action={<Link to="/feedback"><Button>Upload CSV</Button></Link>}
        />
      </>
    )
  }

  const sentimentData = Object.entries(charts?.sentiment_distribution ?? {}).map(([name, value]) => ({ name, value }))
  const priorityData = Object.entries(charts?.priority_distribution ?? {}).map(([name, value]) => ({ name, value }))
  const topicData = (charts?.topic_distribution ?? []).slice(0, 8)
  const categoryData = charts?.category_distribution ?? []
  const running = job?.status === 'running' || job?.status === 'pending'

  return (
    <>
      <PageHeader
        title="Overview"
        description="Current state of customer feedback, calculated from your live dataset."
        actions={
          <>
            <Button variant="secondary" onClick={() => void loadAll()}><RefreshCw size={15} /> Refresh</Button>
            <Button onClick={runAnalysis} disabled={running}><Play size={15} /> {running ? 'Analyzing…' : 'Run analysis'}</Button>
          </>
        }
      />

      {running && job && (
        <Card className="mb-6 border-sky-200 bg-sky-50">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-sm font-semibold text-sky-900">Analysis running</div>
              <div className="text-xs text-sky-700">{job.message}</div>
            </div>
            <div className="text-sm text-sky-800">
              {job.processed ?? 0} / {job.total ?? 0}
              <div className="mt-1 h-1.5 w-40 overflow-hidden rounded bg-sky-200">
                <div className="h-full bg-sky-600 transition-all" style={{ width: `${job.total ? ((job.processed ?? 0) / job.total) * 100 : 0}%` }} />
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* KPI cards: 5 primary + secondary stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard label="Total records" value={summary.total_records.toLocaleString()} accent="#4338ca" />
        <KpiCard label="Unique texts" value={summary.unique_texts.toLocaleString()} hint={`${summary.duplicate_records.toLocaleString()} duplicates preserved`} accent="#0ea5e9" />
        <KpiCard label="Positive" value={summary.positive.toLocaleString()} accent="#10b981" />
        <KpiCard label="Negative" value={summary.negative.toLocaleString()} accent="#e11d48" />
        <KpiCard label="High-priority issues" value={summary.high_priority_issues.toLocaleString()} accent="#f97316" />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard label="Neutral" value={summary.neutral.toLocaleString()} />
        <KpiCard label="Distinct issues" value={summary.distinct_issues.toLocaleString()} />
        <KpiCard label="Completion" value={`${Math.round(summary.completion_rate * 100)}%`} hint={`${summary.pending_records} awaiting analysis`} />
        <KpiCard label="Failed" value={summary.failed_records.toLocaleString()} />
      </div>

      {/* Charts */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-navy-950">Sentiment distribution</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={sentimentData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                {sentimentData.map((d) => <PieCell key={d.name} fill={SENT_COLORS[d.name] ?? '#94a3b8'} />)}
              </Pie>
              <Tooltip formatter={(v, n) => [Number(v).toLocaleString(), n ?? '']} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-navy-950">Original category distribution</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={categoryData} layout="vertical" margin={{ left: 8, right: 12 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="category" width={110} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [Number(v).toLocaleString(), 'Records']} />
              <Bar dataKey="count" fill="#4338ca" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-navy-950">Priority distribution</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={priorityData} margin={{ left: -18 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip formatter={(v) => [Number(v).toLocaleString(), 'Issues']} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {priorityData.map((d) => <Cell key={d.name} fill={PRIORITY_COLORS[d.name] ?? '#94a3b8'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-navy-950">Most frequently reported issues</h2>
          <ResponsiveContainer width="100%" height={Math.max(220, topicData.length * 34)}>
            <BarChart data={topicData} layout="vertical" margin={{ left: 4, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="topic" width={200} tick={{ fontSize: 10.5 }} />
              <Tooltip formatter={(v) => [Number(v).toLocaleString(), 'Records']} />
              <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-navy-950">Trends over time</h2>
          {charts?.trend ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={charts.trend}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="positive" stackId="a" fill="#10b981" />
                <Bar dataKey="neutral" stackId="a" fill="#94a3b8" />
                <Bar dataKey="negative" stackId="a" fill="#e11d48" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[220px] flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 px-4 text-center">
              <AlertTriangle size={22} className="mb-2 text-amber-500" aria-hidden="true" />
              <p className="text-xs leading-relaxed text-slate-500">{charts?.trend_unavailable_reason ?? 'No timestamp data available.'}</p>
            </div>
          )}
        </Card>
      </div>

      {/* Important issues */}
      <Card className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-navy-950">Most important issues</h2>
          <Link to="/recommendations" className="text-sm font-medium text-navy-600 hover:underline">View all recommendations →</Link>
        </div>
        {issues.length === 0 ? (
          <p className="text-sm text-slate-500">No issues identified yet — run the analysis first.</p>
        ) : (
          <div className="overflow-x-auto thin-scroll">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-4">Issue</th>
                  <th className="py-2 pr-4">Records</th>
                  <th className="py-2 pr-4">Negative</th>
                  <th className="py-2 pr-4">Priority</th>
                  <th className="py-2 pr-4">Why it matters</th>
                  <th className="py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {issues.map((iss) => (
                  <tr key={iss.id} className="border-b border-slate-100 align-top">
                    <td className="max-w-[220px] py-3 pr-4 font-medium text-navy-950">{iss.title}</td>
                    <td className="py-3 pr-4">{iss.metrics?.record_count?.toLocaleString()}</td>
                    <td className="py-3 pr-4">{Math.round((iss.metrics?.negative_ratio ?? 0) * 100)}%</td>
                    <td className="py-3 pr-4"><PriorityBadge value={iss.priority} /></td>
                    <td className="max-w-[280px] py-3 pr-4 text-xs text-slate-500">{iss.description}</td>
                    <td className="py-3">
                      <Link to={`/recommendations?issue=${iss.id}`} className="text-sm font-medium text-navy-600 hover:underline">View</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Quick actions */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { to: '/feedback', icon: Upload, title: 'Upload a CSV', body: 'Import feedback in seconds.' },
          { to: '/feedback?add=1', icon: FileText, title: 'Add feedback', body: 'Submit a single review manually.' },
          { to: '/issues', icon: AlertTriangle, title: 'High-priority issues', body: 'Review and track critical items.' },
          { to: '/reports', icon: FileBarChart, title: 'Generate a report', body: 'Export a PDF or CSV insight pack.' },
        ].map(({ to, icon: Icon, title, body }) => (
          <Link key={to} to={to}>
            <Card className="h-full transition-colors hover:border-navy-300 hover:shadow">
              <Icon size={20} className="text-navy-600" aria-hidden="true" />
              <div className="mt-2 text-sm font-semibold text-navy-950">{title}</div>
              <div className="text-xs text-slate-500">{body}</div>
            </Card>
          </Link>
        ))}
      </div>
    </>
  )
}

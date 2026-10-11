import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Upload, FileText, X, Download, ChevronLeft, ChevronRight, Eye } from 'lucide-react'
import { api, downloadFile } from '../lib/api'
import type { Facets, FeedbackItem, FeedbackPage, JobStatus } from '../lib/types'
import { Button, Card, EmptyState, PageHeader, PriorityBadge, SentimentBadge, Spinner, StatusBadge, trunc } from '../components/ui'
import { useToast } from '../lib/toast'

type ImportResult = {
  imported_rows: number
  duplicate_records_preserved: number
  invalid_rows: number
  errors: string[]
  message: string
}

export default function FeedbackExplorer() {
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<FeedbackPage | null>(null)
  const [facets, setFacets] = useState<Facets | null>(null)
  const [loading, setLoading] = useState(true)
  const [job, setJob] = useState<JobStatus | null>(null)
  const [detail, setDetail] = useState<FeedbackItem | null>(null)
  const [importing, setImporting] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [mode, setMode] = useState<'append' | 'replace'>('append')
  const [showReplaceConfirm, setShowReplaceConfirm] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // Manual form
  const [manualOpen, setManualOpen] = useState(params.get('add') === '1')
  const [manualText, setManualText] = useState('')
  const [manualCategory, setManualCategory] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const page = Number(params.get('page') ?? '1')
  const q = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const sentiment = params.get('sentiment') ?? ''
  const topic = params.get('topic') ?? ''
  const priority = params.get('priority') ?? ''
  const status = params.get('status') ?? ''

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const qs = new URLSearchParams()
      if (q) qs.set('q', q)
      if (category) qs.set('category', category)
      if (sentiment) qs.set('sentiment', sentiment)
      if (topic) qs.set('topic', topic)
      if (priority) qs.set('priority', priority)
      if (status) qs.set('status', status)
      qs.set('page', String(page))
      qs.set('page_size', '25')
      const [pageData, facetData, jobData] = await Promise.all([
        api.get<FeedbackPage>(`/api/feedback?${qs.toString()}`),
        api.get<Facets>('/api/feedback/facets'),
        api.get<JobStatus>('/api/analytics/job'),
      ])
      setData(pageData)
      setFacets(facetData)
      setJob(jobData)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load feedback', 'error')
    } finally {
      setLoading(false)
    }
  }, [q, category, sentiment, topic, priority, status, page, toast])

  useEffect(() => { void load() }, [load])

  // Poll while analysis is running so rows light up
  useEffect(() => {
    if (job?.status !== 'running' && job?.status !== 'pending') return
    const t = window.setInterval(() => void load(), 3000)
    return () => window.clearInterval(t)
  }, [job?.status, load])

  const hasFilters = Boolean(q || category || sentiment || topic || priority || status)

  const doImport = async (file: File) => {
    setImporting(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('mode', mode)
      const res = await api.post<ImportResult>('/api/feedback/import', fd)
      toast(res.message, 'success')
      setShowReplaceConfirm(false)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Import failed', 'error')
    } finally {
      setImporting(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const onFilePicked = (file: File | undefined) => {
    if (!file) return
    if (mode === 'replace') { setShowReplaceConfirm(true); return }
    void doImport(file)
  }

  const submitManual = async () => {
    if (manualText.trim().length < 3) {
      toast('Review text must be at least 3 characters.', 'error')
      return
    }
    setSubmitting(true)
    try {
      const res = await api.post<{ id: number; is_duplicate_text: boolean; message: string }>('/api/feedback', {
        review_text: manualText.trim(),
        original_category: manualCategory.trim() || null,
      })
      toast(res.is_duplicate_text ? `${res.message} (duplicate text flagged)` : res.message)
      setManualText('')
      setManualCategory('')
      setManualOpen(false)
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Submission failed', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Feedback Explorer"
        description="Search, filter, and manage every feedback record. Original dataset fields are preserved verbatim."
        actions={
          <>
            <Button variant="secondary" onClick={() => downloadFile('/api/reports/export/feedback.csv' + (hasFilters ? `?${new URLSearchParams(Object.fromEntries(params)).toString()}` : ''), 'feedback-export.csv')}>
              <Download size={15} /> Export CSV
            </Button>
            <Button onClick={() => setManualOpen(!manualOpen)}><FileText size={15} /> Add feedback</Button>
          </>
        }
      />

      {/* Manual submission */}
      {manualOpen && (
        <Card className="mb-5 border-navy-200">
          <h2 className="mb-3 text-sm font-semibold text-navy-950">Submit feedback manually</h2>
          <div className="grid gap-3">
            <div>
              <label htmlFor="manual-review" className="mb-1 block text-xs font-medium text-slate-600">Review text *</label>
              <textarea
                id="manual-review"
                value={manualText}
                onChange={(e) => setManualText(e.target.value)}
                rows={3}
                maxLength={10000}
                placeholder="Paste or write the customer's feedback…"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-navy-500 focus:outline-none"
              />
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label htmlFor="manual-cat" className="mb-1 block text-xs font-medium text-slate-600">Original category (optional)</label>
                <input
                  id="manual-cat"
                  value={manualCategory}
                  onChange={(e) => setManualCategory(e.target.value)}
                  placeholder="e.g. Product Feedback"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-navy-500 focus:outline-none"
                />
              </div>
              <Button onClick={() => void submitManual()} disabled={submitting || manualText.trim().length < 3}>
                {submitting ? 'Saving…' : 'Save & analyze'}
              </Button>
              <span className="text-xs text-slate-400">Saved feedback is analyzed automatically.</span>
            </div>
          </div>
        </Card>
      )}

      {/* Upload area */}
      <Card className="mb-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-navy-950">Import CSV</h2>
            <p className="text-xs text-slate-500">
              Required columns: <code className="rounded bg-slate-100 px-1">review</code>, <code className="rounded bg-slate-100 px-1">category</code>.
              Duplicate texts are preserved and flagged, not discarded.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label htmlFor="import-mode" className="text-xs font-medium text-slate-600">Import mode</label>
            <select
              id="import-mode"
              value={mode}
              onChange={(e) => setMode(e.target.value as 'append' | 'replace')}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="append">Append to current data</option>
              <option value="replace">Replace current data</option>
            </select>
          </div>
        </div>
        <div
          className={`mt-4 flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors ${
            dragOver ? 'border-navy-500 bg-navy-50' : 'border-slate-300'
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); onFilePicked(e.dataTransfer.files[0]) }}
        >
          <Upload size={22} className="mb-2 text-navy-500" aria-hidden="true" />
          <p className="text-sm text-slate-600">Drag &amp; drop a CSV here, or</p>
          <div className="mt-2">
            <Button onClick={() => fileRef.current?.click()} disabled={importing}>
              {importing ? 'Importing…' : 'Choose file'}
            </Button>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => onFilePicked(e.target.files?.[0])}
            aria-label="Choose CSV file"
          />
          {importing && <div className="mt-3"><Spinner label="Parsing, validating and importing — analysis will start automatically…" /></div>}
        </div>
      </Card>

      {/* Replace confirmation */}
      {showReplaceConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" role="dialog" aria-modal="true">
          <Card className="max-w-md">
            <h3 className="text-base font-semibold text-navy-950">Replace existing data?</h3>
            <p className="mt-2 text-sm text-slate-600">
              This will permanently delete all {data?.total ?? 0} current feedback records and their analysis before importing the new file.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setShowReplaceConfirm(false)}>Cancel</Button>
              <Button variant="danger" onClick={() => { const f = fileRef.current?.files?.[0]; if (f) void doImport(f); setShowReplaceConfirm(false) }}>
                Delete &amp; replace
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Search + filters */}
      <Card className="mb-4">
        <div className="flex flex-col gap-3">
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              defaultValue={q}
              placeholder="Search review text or category (case-insensitive, partial matches work)…"
              onChange={(e) => {
                const v = e.target.value
                window.clearTimeout((window as unknown as { __searchTimer?: number }).__searchTimer)
                ;(window as unknown as { __searchTimer?: number }).__searchTimer = window.setTimeout(() => setParam('q', v), 350)
              }}
              aria-label="Search feedback"
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-navy-500 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <FilterSelect label="Original category" value={category} options={facets?.categories ?? []} onChange={(v) => setParam('category', v)} />
            <FilterSelect label="Sentiment" value={sentiment} options={facets?.sentiments ?? []} onChange={(v) => setParam('sentiment', v)} />
            <FilterSelect label="Topic" value={topic} options={facets?.topics ?? []} onChange={(v) => setParam('topic', v)} />
            <FilterSelect label="Priority" value={priority} options={facets?.priorities ?? []} onChange={(v) => setParam('priority', v)} />
            <FilterSelect label="Analysis status" value={status} options={facets?.statuses ?? []} onChange={(v) => setParam('status', v)} />
          </div>
          {hasFilters && (
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={() => setParams(new URLSearchParams())}><X size={14} /> Clear all filters</Button>
              <span className="text-xs text-slate-500">{data?.total.toLocaleString()} matching records</span>
            </div>
          )}
        </div>
      </Card>

      {/* Table */}
      {loading && !data ? (
        <Spinner label="Loading feedback…" />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No results match your filters' : 'No feedback yet'}
          body={hasFilters ? 'Try adjusting the filters or clear them to see all records.' : 'Import a CSV or submit feedback manually to get started.'}
          action={hasFilters ? <Button onClick={() => setParams(new URLSearchParams())}>Clear all filters</Button> : undefined}
        />
      ) : (
        <Card className="p-0">
          <div className="overflow-x-auto thin-scroll">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Review</th>
                  <th className="px-3 py-3">Original category</th>
                  <th className="px-3 py-3">Sentiment</th>
                  <th className="px-3 py-3">Topic</th>
                  <th className="px-3 py-3">Priority</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((fb) => (
                  <tr key={fb.id} className="border-b border-slate-100 align-top hover:bg-slate-50/60">
                    <td className="max-w-[360px] px-4 py-3">
                      <div className="text-slate-800">{trunc(fb.review_text, 130)}</div>
                      <div className="mt-1 flex gap-2 text-[11px] text-slate-400">
                        <span>#{fb.id}</span>
                        {fb.is_duplicate_text && <span className="rounded bg-amber-50 px-1 text-amber-700">duplicate text</span>}
                        <span>{fb.source}</span>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-600">{fb.original_category ?? '—'}</td>
                    <td className="px-3 py-3">
                      <SentimentBadge value={fb.sentiment} />
                      {fb.sentiment_score !== null && (
                        <div className="mt-1 text-[11px] text-slate-400">score {fb.sentiment_score.toFixed(2)}</div>
                      )}
                    </td>
                    <td className="max-w-[180px] px-3 py-3 text-xs text-slate-600">{fb.topic ?? '—'}</td>
                    <td className="px-3 py-3"><PriorityBadge value={fb.priority} /></td>
                    <td className="px-3 py-3"><StatusBadge value={fb.analysis_status} /></td>
                    <td className="px-3 py-3">
                      <button onClick={() => setDetail(fb)} className="inline-flex items-center gap-1 text-xs font-medium text-navy-600 hover:underline" aria-label={`View review #${fb.id}`}>
                        <Eye size={13} /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
            <span className="text-xs text-slate-500">
              Page {data.page} of {data.pages} — {data.total.toLocaleString()} records
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={data.page <= 1} onClick={() => setParam('page', String(page - 1))}>
                <ChevronLeft size={14} /> Prev
              </Button>
              <Button variant="secondary" disabled={data.page >= data.pages} onClick={() => setParam('page', String(page + 1))}>
                Next <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Detail modal */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" role="dialog" aria-modal="true" aria-label="Review detail">
          <Card className="max-h-[85vh] w-full max-w-2xl overflow-y-auto">
            <div className="mb-3 flex items-start justify-between gap-4">
              <h3 className="text-base font-semibold text-navy-950">Review #{detail.id}</h3>
              <button onClick={() => setDetail(null)} aria-label="Close detail" className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
            </div>
            <p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-800">{detail.review_text}</p>
            <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div><dt className="text-xs font-medium text-slate-500">Original category</dt><dd>{detail.original_category ?? '—'}</dd></div>
              <div><dt className="text-xs font-medium text-slate-500">Sentiment</dt><dd className="mt-0.5"><SentimentBadge value={detail.sentiment} /> {detail.sentiment_score !== null && <span className="ml-1 text-xs text-slate-400">({detail.sentiment_score.toFixed(2)}, conf. {detail.sentiment_confidence?.toFixed(2)})</span>}</dd></div>
              <div><dt className="text-xs font-medium text-slate-500">Identified topic</dt><dd>{detail.topic ?? '—'}</dd></div>
              <div><dt className="text-xs font-medium text-slate-500">Refined category</dt><dd>{detail.refined_category ?? '—'}</dd></div>
              <div><dt className="text-xs font-medium text-slate-500">Priority</dt><dd><PriorityBadge value={detail.priority} /></dd></div>
              <div><dt className="text-xs font-medium text-slate-500">Analysis method</dt><dd className="text-xs text-slate-600">{detail.evidence ?? '—'}</dd></div>
            </dl>
          </Card>
        </div>
      )}
    </>
  )
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  if (options.length === 0) return null
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-500">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        className="w-full rounded-lg border border-slate-300 px-2.5 py-2 text-sm focus:border-navy-500 focus:outline-none"
      >
        <option value="">All</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

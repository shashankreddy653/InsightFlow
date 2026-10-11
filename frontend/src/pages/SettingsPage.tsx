import { useCallback, useEffect, useState } from 'react'
import { Plug, Play, FlaskConical, KeyRound, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api'
import type { AdaptionStatus, AppSettings } from '../lib/types'
import { Button, Card, PageHeader, Spinner } from '../components/ui'
import { useToast } from '../lib/toast'

type EvalResult = {
  sentiment_accuracy: number
  topic_accuracy: number
  clear_total: number
  ambiguous_total: number
  ambiguous_sentiment_agreement: number
}

export default function SettingsPage() {
  const toast = useToast()
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [adaption, setAdaption] = useState<AdaptionStatus | null>(null)
  const [weights, setWeights] = useState<Record<string, number>>({})
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [evaluating, setEvaluating] = useState(false)
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null)
  const [datasetPreview, setDatasetPreview] = useState<{ row_count: number; preview: string[] } | null>(null)

  const load = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([
        api.get<AppSettings>('/api/settings'),
        api.get<AdaptionStatus>('/api/integrations/adaption'),
      ])
      setSettings(s)
      setWeights(s.priority_weights)
      setAdaption(a)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to load settings', 'error')
    }
  }, [toast])

  useEffect(() => { void load() }, [load])

  const saveWeights = async () => {
    setSaving(true)
    try {
      await api.post('/api/settings', {
        weight_frequency: weights.frequency,
        weight_negative: weights.negative,
        weight_severity: weights.severity,
        weight_trend: weights.trend,
      })
      const res = await api.post<{ weights_applied: Record<string, number> }>('/api/settings/rescore')
      toast(`Weights saved and all issues re-scored (trend weight applies only when timestamps exist).`)
      await load()
      console.info('weights applied', res.weights_applied)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to save settings', 'error')
    } finally {
      setSaving(false)
    }
  }

  const runAdaption = async () => {
    setRunning(true)
    try {
      const res = await api.post<{ status: string; detail: string }>('/api/integrations/adaption/run')
      if (res.status === 'succeeded') toast(`Adaption run succeeded: ${res.detail}`)
      else if (res.status === 'not_configured') toast(`Not configured: ${res.detail}`, 'error')
      else toast(`Run failed: ${res.detail}`, 'error')
      await load()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Adaption run failed', 'error')
    } finally {
      setRunning(false)
    }
  }

  const evaluate = async () => {
    setEvaluating(true)
    try {
      const res = await api.post<EvalResult>('/api/integrations/adaption/evaluate')
      setEvalResult(res)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Evaluation failed', 'error')
    } finally {
      setEvaluating(false)
    }
  }

  const previewDataset = async () => {
    try {
      const res = await api.get<{ row_count: number; preview: string[] }>('/api/integrations/adaption/dataset')
      setDatasetPreview(res)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to build dataset preview', 'error')
    }
  }

  if (!settings || !adaption) return <Spinner label="Loading settings…" />

  const weightEntries = Object.entries(weights)

  return (
    <>
      <PageHeader
        title="Settings & Integrations"
        description="Configure the transparent priority-scoring weights and manage the Adaption integration."
      />

      {/* Priority weights */}
      <Card className="mb-6">
        <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-navy-950">
          <KeyRound size={16} className="text-navy-600" aria-hidden="true" /> Priority scoring weights
        </h2>
        <p className="mb-4 max-w-2xl text-xs leading-relaxed text-slate-500">
          Priority Score = w₁·Frequency + w₂·Negative ratio + w₃·Severity + w₄·Trend.
          When trend data is unavailable (no timestamps), its weight is renormalized across the
          remaining factors and the UI states which factors were used. Weights are automatically
          rebalanced to sum to 1.0 when saved.
        </p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {weightEntries.map(([k, v]) => (
            <div key={k}>
              <label htmlFor={`w-${k}`} className="mb-1 block text-xs font-medium capitalize text-slate-600">
                {k === 'negative' ? 'Negative sentiment' : k} — {Math.round(v * 100)}%
              </label>
              <input
                id={`w-${k}`}
                type="range"
                min={0}
                max={100}
                value={Math.round(v * 100)}
                onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) / 100 })}
                className="w-full accent-indigo-600"
              />
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={() => void saveWeights()} disabled={saving}>{saving ? 'Saving…' : 'Save & re-score issues'}</Button>
          <span className="text-xs text-slate-400">
            Sum: {Math.round(weightEntries.reduce((a, [, v]) => a + v, 0) * 100)}% (rebalanced on save)
          </span>
        </div>
      </Card>

      {/* Adaption integration */}
      <Card className="mb-6">
        <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-navy-950">
          <Plug size={16} className="text-navy-600" aria-hidden="true" /> Adaption integration
        </h2>
        <p className="mb-4 max-w-3xl text-xs leading-relaxed text-slate-500">
          <b>Task in InsightFlow:</b> {adaption.task}
          <br />
          <b>Workflow:</b> {adaption.workflow} — via the official <code>adaption</code> Python SDK
          (upload instruction dataset → column mapping → estimate → adapt → wait → download → evaluate
          against the {adaption.reference_examples}-example hand-labeled reference subset).
        </p>

        <div className="grid gap-3 sm:grid-cols-3">
          <StatusTile
            ok={adaption.configured}
            label="API key"
            value={adaption.configured ? 'Configured (ADAPTION_API_KEY set)' : 'Not configured'}
          />
          <StatusTile
            ok={adaption.sdk_installed}
            label="Python SDK"
            value={adaption.sdk_installed ? 'Installed' : 'Not installed (pip install adaption)'}
          />
          <StatusTile
            ok={adaption.last_run?.status === 'succeeded'}
            label="Last run"
            value={adaption.last_run ? `${adaption.last_run.status} (${adaption.last_run.step ?? '—'})` : 'Never run'}
            neutral={!adaption.last_run}
          />
        </div>

        {adaption.last_run?.detail && (
          <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            <b>Last run detail:</b> {adaption.last_run.detail}
            {adaption.last_run.dataset_id && <> · dataset <code>{adaption.last_run.dataset_id}</code></>}
            {adaption.last_run.run_id && <> · run <code>{adaption.last_run.run_id}</code></>}
          </p>
        )}

        {!adaption.configured && adaption.setup_instructions && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
            <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-amber-900">
              <AlertTriangle size={14} aria-hidden="true" /> Setup required to run Adaptive Data
            </div>
            <ol className="list-inside list-decimal space-y-0.5 text-xs text-amber-800">
              {adaption.setup_instructions.map((s, i) => <li key={i}>{s}</li>)}
            </ol>
            <p className="mt-2 text-xs text-amber-800">
              The rest of the application — import, analysis, insights, recommendations, tracking,
              reports — works fully without Adaption. Nothing is faked while it is unconfigured.
            </p>
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => void runAdaption()} disabled={running || !adaption.configured}>
            <Play size={15} /> {running ? 'Running workflow…' : 'Run Adaptive Data workflow'}
          </Button>
          <Button variant="secondary" onClick={() => void evaluate()} disabled={evaluating}>
            <FlaskConical size={15} /> {evaluating ? 'Evaluating…' : 'Run local pipeline evaluation'}
          </Button>
          <Button variant="secondary" onClick={() => void previewDataset()}>Preview instruction dataset</Button>
        </div>

        {evalResult && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Mini label="Sentiment accuracy" value={`${Math.round(evalResult.sentiment_accuracy * 100)}%`} sub={`${evalResult.clear_total} clear items`} />
            <Mini label="Topic accuracy" value={`${Math.round(evalResult.topic_accuracy * 100)}%`} sub={`${evalResult.clear_total} clear items`} />
            <Mini label="Ambiguous agreement" value={`${Math.round(evalResult.ambiguous_sentiment_agreement * 100)}%`} sub={`${evalResult.ambiguous_total} mixed items`} />
            <Mini label="Reference size" value={evalResult.clear_total + evalResult.ambiguous_total} sub="hand-labeled" />
          </div>
        )}

        {datasetPreview && (
          <div className="mt-4">
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Instruction dataset preview ({datasetPreview.row_count} unique analyzed texts)
            </h4>
            <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-[11px] leading-relaxed text-slate-100 thin-scroll">
              {datasetPreview.preview.join('\n')}
            </pre>
          </div>
        )}
      </Card>

      {/* AI provider config guidance */}
      <Card>
        <h2 className="mb-1 text-sm font-semibold text-navy-950">AI provider configuration (developer)</h2>
        <p className="text-xs leading-relaxed text-slate-500">
          Sentiment (VADER) and topic/similarity analysis run locally and require no keys.
          Optionally set <code>INSIGHTFLOW_LLM_API_KEY</code> (plus <code>INSIGHTFLOW_LLM_BASE_URL</code> /{' '}
          <code>INSIGHTFLOW_LLM_MODEL</code>) in <code>backend/.env</code> to let an OpenAI-compatible
          model refine recommendation wording — cards are then labelled “LLM-generated” instead of
          “Template engine”. Secrets stay server-side; nothing is exposed to the browser.
          Current status: LLM recommendations <b>{settings.llm_configured ? 'enabled' : 'disabled (using transparent templates)'}</b>.
        </p>
      </Card>
    </>
  )
}

function StatusTile({ ok, label, value, neutral }: { ok: boolean; label: string; value: string; neutral?: boolean }) {
  return (
    <div className={`rounded-lg border px-3 py-2.5 ${neutral ? 'border-slate-200 bg-slate-50' : ok ? 'border-emerald-200 bg-emerald-50' : 'border-rose-200 bg-rose-50'}`}>
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        {neutral ? <AlertTriangle size={13} className="text-slate-400" /> : ok ? <CheckCircle2 size={13} className="text-emerald-600" /> : <XCircle size={13} className="text-rose-600" />}
        {label}
      </div>
      <div className={`mt-0.5 text-sm font-medium ${neutral ? 'text-slate-700' : ok ? 'text-emerald-900' : 'text-rose-900'}`}>{value}</div>
    </div>
  )
}

function Mini({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="text-[11px] font-medium text-slate-500">{label}</div>
      <div className="text-base font-semibold text-navy-950">{value}</div>
      {sub && <div className="text-[11px] text-slate-400">{sub}</div>}
    </div>
  )
}

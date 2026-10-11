export interface Summary {
  total_records: number
  unique_texts: number
  duplicate_records: number
  analyzed_records: number
  pending_records: number
  failed_records: number
  completion_rate: number
  positive: number
  negative: number
  neutral: number
  high_priority_issues: number
  distinct_issues: number
  records_with_timestamps: number
  trend_available: boolean
}

export interface Charts {
  sentiment_distribution: Record<string, number>
  category_distribution: { category: string; count: number }[]
  topic_distribution: { topic: string; count: number }[]
  priority_distribution: Record<string, number>
  analysis_status_distribution: Record<string, number>
  trend: { month: string; positive?: number; negative?: number; neutral?: number; total: number }[] | null
  trend_unavailable_reason: string | null
}

export interface FeedbackItem {
  id: number
  review_text: string
  original_category: string | null
  sentiment: string | null
  sentiment_score: number | null
  sentiment_confidence: number | null
  topic: string | null
  refined_category: string | null
  evidence: string | null
  analysis_status: string
  is_duplicate_text: boolean
  source: string
  issue_id: number | null
  priority: string | null
  created_at: string | null
}

export interface FeedbackPage {
  items: FeedbackItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface Facets {
  categories: string[]
  sentiments: string[]
  topics: string[]
  priorities: string[]
  statuses: string[]
}

export interface JobStatus {
  id?: number
  status: string
  total?: number
  processed?: number
  failed?: number
  message?: string | null
  started_at?: string | null
  finished_at?: string | null
}

export interface IssueMetrics {
  record_count?: number
  unique_count?: number
  sentiment_breakdown?: Record<string, number>
  negative_ratio?: number
  category_breakdown?: Record<string, number>
  factors_used?: string[]
  factors_unavailable?: string[]
  representative_text?: string
}

export interface Issue {
  id: number
  title: string
  description: string | null
  topic: string | null
  priority: string
  system_priority?: string
  priority_score: number
  score_breakdown?: {
    components?: Record<string, number>
    weights_used?: Record<string, number>
    configured_weights?: Record<string, number>
    severity_base?: number
  }
  metrics: IssueMetrics
  recommendation: string | null
  recommendation_source: string | null
  success_metric: string | null
  saved: boolean
  status: string
  action_plan?: string | null
  resolution_notes?: string | null
  notes?: { id: number; note_text: string; created_at: string | null }[] | null
  feedback_count?: number
  factors_used?: string[]
  factors_unavailable?: string[]
  created_at?: string | null
  updated_at?: string | null
}

export interface IssueDetail extends Issue {
  notes: { id: number; note_text: string; created_at: string | null }[]
  evidence: {
    feedback_id: number
    review_text: string
    original_category: string | null
    sentiment: string | null
    sentiment_score: number | null
    topic: string | null
  }[]
}

export interface ReportMeta {
  id: number
  title: string
  report_type: string
  filters: Record<string, unknown>
  created_at: string | null
}

export interface AdaptionStatus {
  configured: boolean
  sdk_installed: boolean
  workflow: string
  task: string
  reference_examples: number
  last_run: {
    id: number
    status: string
    step: string | null
    dataset_id: string | null
    run_id: string | null
    detail: string | null
    result_summary: Record<string, unknown> | null
    created_at: string | null
  } | null
  setup_instructions?: string[]
}

export interface AppSettings {
  priority_weights: Record<string, number>
  llm_configured: boolean
  adaption_configured: boolean
}

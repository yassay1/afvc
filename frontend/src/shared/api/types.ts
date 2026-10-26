export interface DeviceListItem {
  assetnum: string
  workorder_count: number
  station_name: string | null
  line: string | null
  brand: string | null
  last_record_time: string | null
}

export interface DeviceListResponse {
  status: string
  message: string
  device_count: number
  devices: DeviceListItem[]
}

export interface HealthResponse {
  status: string
  data_profile: 'demo' | 'production'
}

export interface DeviceDiagnosisResponse {
  status: string
  message: string
  assetnum: string
  device_profile?: {
    assetnum: string
    station_name: string | null
    line: string | null
    brand: string | null
    subsystem: string | null
    history_workorder_count: number | null
    last_record_time: string | null
  }
  history_summary?: {
    returned_history_count: number | null
    recent_descriptions: string[]
    top_fault_descriptions: { description: string; count: number }[]
  }
  risk_prediction?: {
    risk_30d: number | null
    risk_90d: number | null
    warning_level: string | null
    warning_reason: string | null
    suggested_inspection_window: string | null
    main_risk_factors: string[]
  }
  maintenance_advice?: {
    recognized_fault_phenomena: string[]
    inspection_suggestions: string[]
    spare_part_suggestions: string[]
  }
  fault_prediction?: {
    status: string
    message: string
    prediction_window_days: number
    most_likely_fault: { fault_name: string; conditional_probability: number } | null
    prediction_statement?: string
  }
  analysis_statement: string
}

export interface MaintenanceSuggestion {
  assetnum: string
  station_name: string | null
  fault_focus: string
  warning_level: string | null
  reasons: string[]
  data_note: string | null
  score: number | null
  suggested_crew_id: string | null
}

export interface MaintenanceSuggestionsResponse {
  status: string
  message: string
  suggestions: MaintenanceSuggestion[]
  ranking_method: string
  prediction_tier: string | null
  model_note: string | null
}

export type MaintenanceTaskStatus = 'planned' | 'in_progress' | 'done' | 'cancelled'

export interface MaintenanceTask {
  id: string
  assetnum: string
  station_name: string | null
  status: MaintenanceTaskStatus
  planned_date: string | null
  fault_focus: string
  priority: number
  assignee_crew_id: string | null
  suggestion_score: number | null
  suggestion_reasons: string[]
  feedback_result: string | null
  feedback_matched_fault: boolean | null
  feedback_followed_suggestion: boolean | null
  feedback_note: string | null
  feedback_at: string | null
}

export interface MaintenanceTasksResponse {
  status: string
  message: string
  tasks: MaintenanceTask[]
  count: number
}

export interface MaintenanceTaskResponse {
  status: string
  message?: string
  task: MaintenanceTask
}

export interface MaintenanceTaskCreateBody {
  assetnum: string
  station_name: string | null
  fault_focus: string
  priority: number
  planned_date: string
  assignee_crew_id: string
  suggestion_score: number | null
  suggestion_reasons: string[]
}

export interface MaintenanceTaskPatchBody {
  priority?: number
  planned_date?: string
  assignee_crew_id?: string
  status?: MaintenanceTaskStatus
}

export interface MaintenanceFeedbackBody {
  result: string
  matched_fault?: boolean | null
  followed_suggestion?: boolean | null
  note?: string | null
}

export interface PendingAction {
  action_id: string
  thread_id: string
  tool_name: string
  status: string
  summary: string
  payload: Record<string, unknown>
  executed: boolean
}

export interface InteractionResponse {
  status: string
  use_case: string | null
  assetnum: string | null
  final_answer: string
  session_id: string
  last_assetnum: string | null
  result: Record<string, unknown> | null
  pending_actions: PendingAction[]
}

export interface PendingActionsResponse {
  session_id: string
  pending_actions: PendingAction[]
}

export interface DataOverviewResponse {
  status: string
  message: string
  data_backend: string | null
  basic_metrics: {
    workorder_count: number
    column_count: number
    device_count: number
    station_count: number
    line_count: number
    brand_count: number
  }
  time_range: { start_time: string | null; end_time: string | null; note: string }
  brand_distribution: { name: string; count: number }[]
  fault_description_top: { name: string; count: number }[]
  line_distribution: { name: string; count: number }[]
  field_note: { current_faildate: string; description: string }
}

export interface HighRiskDevice {
  assetnum: string
  station_name: string | null
  line: string | null
  brand: string | null
  risk_30d: number | null
  risk_90d: number | null
  warning_level: string | null
  suggested_inspection_window: string | null
  main_risk_factors: string[]
}

export interface HighRiskResponse {
  status: string
  message: string
  devices: HighRiskDevice[]
  prediction_source: string
  prediction_tier: string
  model_note: string
}

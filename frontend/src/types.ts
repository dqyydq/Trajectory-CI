export type Filters = {
  tenants: string[];
  models: string[];
};

export type Summary = {
  call_count: number;
  error_count: number;
  in_progress_count: number;
  cost_usd: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  total_tokens: number;
  trace_count: number;
};

export type SpanRecord = {
  span_id: string;
  trace_id: string;
  session_id?: string | null;
  tenant_id?: string | null;
  parent_span_id?: string | null;
  span_type?: string | null;
  model?: string | null;
  status: string;
  is_stream?: boolean;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  cost_usd?: number | null;
  latency_ms?: number | null;
  started_at?: string | null;
  ended_at?: string | null;
  request_body?: unknown;
  response_body?: unknown;
  error_message?: string | null;
};

export type TrendPoint = {
  hour: string;
  call_count: number;
  cost_usd: number;
  avg_latency_ms: number;
};

export type ModelBreakdown = {
  model: string;
  calls: number;
  errors: number;
  cost_usd: number;
  avg_latency_ms: number;
};

export type AlertRecord = {
  rule: string;
  severity: string;
  value: number;
  detail: string;
};

export type EvalReport = {
  report_id: string;
  task_set_name: string;
  run_id_a: string;
  run_id_b: string;
  created_at: string;
  summary: Record<string, number>;
};

export type EvalTaskResult = {
  task_id: string;
  run_a_status: string;
  run_a_judge_score?: number | null;
  run_b_status: string;
  run_b_judge_score?: number | null;
  regressed: boolean;
  detail: Record<string, any>;
};

export type DashboardState = {
  hours: number;
  tenantId: string;
  model: string;
  status: string;
  traceId: string;
  sessionId: string;
};
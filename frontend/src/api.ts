import type {
  AlertRecord,
  EvalReport,
  EvalTaskResult,
  Filters,
  ModelBreakdown,
  SpanRecord,
  Summary,
  TrendPoint,
} from "./types";

const params = (input: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(input).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  const value = search.toString();
  return value ? `?${value}` : "";
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  filters: () => getJson<Filters>("/api/dashboard/filters"),
  summary: (query: { tenant_id?: string; model?: string; hours: number }) =>
    getJson<Summary>(`/api/dashboard/summary${params(query)}`),
  spans: (query: {
    trace_id?: string;
    session_id?: string;
    tenant_id?: string;
    model?: string;
    status?: string;
    hours: number;
  }) => getJson<SpanRecord[]>(`/api/dashboard/spans${params(query)}`),
  trace: (traceId: string) => getJson<SpanRecord[]>(`/api/dashboard/traces/${traceId}`),
  costTrend: (query: { tenant_id?: string; model?: string; hours: number }) =>
    getJson<TrendPoint[]>(`/api/dashboard/cost-trend${params(query)}`),
  modelBreakdown: (query: { tenant_id?: string; hours: number }) =>
    getJson<ModelBreakdown[]>(`/api/dashboard/model-breakdown${params(query)}`),
  alerts: (query: { tenant_id?: string; model?: string; hours: number }) =>
    getJson<AlertRecord[]>(`/api/dashboard/alerts${params(query)}`),
  evalReports: () => getJson<EvalReport[]>("/api/dashboard/eval-reports"),
  evalTasks: (reportId: string) => getJson<EvalTaskResult[]>(`/api/dashboard/eval-reports/${reportId}/tasks`),
};
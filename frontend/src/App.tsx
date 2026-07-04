import { Activity, AlertTriangle, BarChart3, GitBranch, Layers, RefreshCcw, Search, Server } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "./api";
import type {
  AlertRecord,
  DashboardState,
  EvalReport,
  EvalTaskResult,
  Filters,
  ModelBreakdown,
  SpanRecord,
  Summary,
  TrendPoint,
} from "./types";

const emptySummary: Summary = {
  call_count: 0,
  error_count: 0,
  in_progress_count: 0,
  cost_usd: 0,
  avg_latency_ms: 0,
  p95_latency_ms: 0,
  total_tokens: 0,
  trace_count: 0,
};

const fmtMoney = (value?: number | null) => `$${Number(value ?? 0).toFixed(4)}`;
const fmtMs = (value?: number | null) => `${Math.round(Number(value ?? 0)).toLocaleString()}ms`;
const fmtNum = (value?: number | null) => Math.round(Number(value ?? 0)).toLocaleString();
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

function query(state: DashboardState) {
  return {
    tenant_id: state.tenantId || undefined,
    model: state.model || undefined,
    status: state.status || undefined,
    trace_id: state.traceId || undefined,
    session_id: state.sessionId || undefined,
    hours: state.hours,
  };
}

function MetricCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone?: string }) {
  return (
    <section className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone ?? ""}`}>{value}</div>
      <div className="metric-detail">{detail}</div>
    </section>
  );
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value ?? null, null, 2)}</pre>;
}

function TraceTree({ spans }: { spans: SpanRecord[] }) {
  const rows = useMemo(() => {
    const byParent = new Map<string | null, SpanRecord[]>();
    const ids = new Set(spans.map((span) => span.span_id));
    spans.forEach((span) => {
      const parent = span.parent_span_id && ids.has(span.parent_span_id) ? span.parent_span_id : null;
      const bucket = byParent.get(parent) ?? [];
      bucket.push(span);
      byParent.set(parent, bucket);
    });
    const output: Array<{ depth: number; span: SpanRecord }> = [];
    const visit = (parent: string | null, depth: number) => {
      (byParent.get(parent) ?? []).forEach((span) => {
        output.push({ depth, span });
        visit(span.span_id, depth + 1);
      });
    };
    visit(null, 0);
    return output;
  }, [spans]);

  if (!rows.length) return <div className="empty-state">No spans found for this trace.</div>;

  return (
    <div className="trace-tree">
      {rows.map(({ depth, span }) => (
        <details className="trace-node" key={span.span_id} style={{ marginLeft: depth * 18 }}>
          <summary>
            <code>{span.span_id}</code>
            <span className={`status status-${span.status}`}>{span.status}</span>
            <span>{span.span_type ?? "llm_call"}</span>
            <span>{span.model ?? "unknown"}</span>
            <span>{span.is_stream ? "stream" : "sync"}</span>
            <span>{span.ended_at ? fmtMs(span.latency_ms) : "open"}</span>
            <span>{fmtMoney(span.cost_usd)}</span>
          </summary>
          <div className="payload-grid">
            <div>
              <h4>Request</h4>
              <JsonBlock value={span.request_body} />
            </div>
            <div>
              <h4>Response</h4>
              <JsonBlock value={span.response_body} />
            </div>
          </div>
          {span.error_message ? <div className="error-box">{span.error_message}</div> : null}
        </details>
      ))}
    </div>
  );
}

function App() {
  const buildLabel = "react-dashboard";
  const [filters, setFilters] = useState<Filters>({ tenants: [], models: [] });
  const [state, setState] = useState<DashboardState>({
    hours: 24,
    tenantId: "",
    model: "",
    status: "",
    traceId: "",
    sessionId: "",
  });
  const [summary, setSummary] = useState<Summary>(emptySummary);
  const [spans, setSpans] = useState<SpanRecord[]>([]);
  const [traceSpans, setTraceSpans] = useState<SpanRecord[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [models, setModels] = useState<ModelBreakdown[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [reports, setReports] = useState<EvalReport[]>([]);
  const [tasks, setTasks] = useState<EvalTaskResult[]>([]);
  const [selectedReport, setSelectedReport] = useState("");
  const [activeTab, setActiveTab] = useState("calls");
  const [draftTraceId, setDraftTraceId] = useState("");
  const [draftSessionId, setDraftSessionId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const q = query(state);
      const [nextFilters, nextSummary, nextSpans, nextTrend, nextModels, nextAlerts, nextReports] = await Promise.all([
        api.filters(),
        api.summary({ tenant_id: q.tenant_id, model: q.model, hours: q.hours }),
        api.spans(q),
        api.costTrend({ tenant_id: q.tenant_id, model: q.model, hours: q.hours }),
        api.modelBreakdown({ tenant_id: q.tenant_id, hours: q.hours }),
        api.alerts({ tenant_id: q.tenant_id, model: q.model, hours: q.hours }),
        api.evalReports(),
      ]);
      setFilters(nextFilters);
      setSummary(nextSummary);
      setSpans(nextSpans);
      setTrend(nextTrend);
      setModels(nextModels);
      setAlerts(nextAlerts);
      setReports(nextReports);
      if (!selectedReport && nextReports.length) setSelectedReport(nextReports[0].report_id);
      if (state.traceId) setTraceSpans(await api.trace(state.traceId));
      else setTraceSpans([]);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : String(exception));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setState((current) => {
        if (current.traceId === draftTraceId && current.sessionId === draftSessionId) return current;
        return { ...current, traceId: draftTraceId, sessionId: draftSessionId };
      });
    }, 450);
    return () => window.clearTimeout(handle);
  }, [draftTraceId, draftSessionId]);

  useEffect(() => {
    void refresh();
  }, [state.hours, state.tenantId, state.model, state.status, state.traceId, state.sessionId]);

  useEffect(() => {
    if (!selectedReport) {
      setTasks([]);
      return;
    }
    api.evalTasks(selectedReport).then(setTasks).catch((exception) => setError(exception instanceof Error ? exception.message : String(exception)));
  }, [selectedReport]);

  const applyFilters = () => {
    if (state.traceId !== draftTraceId || state.sessionId !== draftSessionId) {
      setState({ ...state, traceId: draftTraceId, sessionId: draftSessionId });
      return;
    }
    void refresh();
  };

  const errorRate = summary.call_count ? summary.error_count / summary.call_count : 0;
  const health = errorRate > 0.2 ? "Watch" : "Nominal";
  const heroDetail = `${state.hours}h / ${state.tenantId || "all tenants"} / ${state.model || "all models"}`;
  const selectedReportRecord = reports.find((report) => report.report_id === selectedReport) ?? reports[0];
  const gate = selectedReportRecord?.summary?.gate;
  const gateStatus = gate?.status ?? "unknown";
  const gateFailures = gate?.failures ?? [];
  const gateSummary = selectedReportRecord?.summary;

  return (
    <main className="app-shell" data-build={buildLabel}>
      <aside className="sidebar">
        <div className="brand-lockup">
          <Server size={20} />
          <div>
            <strong>Trajectory CI</strong>
            <span>Agent regression dashboard</span>
          </div>
        </div>

        <label>
          Time window
          <select value={state.hours} onChange={(event) => setState({ ...state, hours: Number(event.target.value) })}>
            {[1, 6, 12, 24, 72, 168].map((hours) => (
              <option key={hours} value={hours}>{hours}h</option>
            ))}
          </select>
        </label>
        <label>
          Tenant
          <select value={state.tenantId} onChange={(event) => setState({ ...state, tenantId: event.target.value })}>
            <option value="">all tenants</option>
            {filters.tenants.map((tenant) => <option key={tenant} value={tenant}>{tenant}</option>)}
          </select>
        </label>
        <label>
          Model
          <select value={state.model} onChange={(event) => setState({ ...state, model: event.target.value })}>
            <option value="">all models</option>
            {filters.models.map((model) => <option key={model} value={model}>{model}</option>)}
          </select>
        </label>
        <label>
          Status
          <select value={state.status} onChange={(event) => setState({ ...state, status: event.target.value })}>
            <option value="">all statuses</option>
            <option value="in_progress">in_progress</option>
            <option value="success">success</option>
            <option value="error">error</option>
          </select>
        </label>
        <label>
          Trace id
          <input value={draftTraceId} onChange={(event) => setDraftTraceId(event.target.value)} placeholder="trace uuid" />
        </label>
        <label>
          Session id
          <input value={draftSessionId} onChange={(event) => setDraftSessionId(event.target.value)} placeholder="session" />
        </label>
        <button className="refresh-button" onClick={applyFilters} disabled={loading}>
          <RefreshCcw size={16} /> Refresh
        </button>
      </aside>

      <section className="content-shell">
        <section className="hero-panel">
          <div>
            <h1>Regression CI for agent changes.</h1>
            <p>Run baseline and candidate agents, get a red or green release gate, then drill into traces, cost, latency, and task diffs.</p>
          </div>
          <div className="target-panel">
            <span>Live target</span>
            <code>{heroDetail}</code>
          </div>
        </section>

        {error ? <div className="error-banner">{error}</div> : null}

        <section className={`gate-panel gate-${gateStatus}`}>
          <div>
            <span className="gate-kicker">Regression gate</span>
            <h2>{gateStatus === "failed" ? "FAILED" : gateStatus === "passed" ? "PASSED" : "No report yet"}</h2>
            <p>{selectedReportRecord ? `${selectedReportRecord.task_set_name}: ${selectedReportRecord.run_id_b} vs ${selectedReportRecord.run_id_a}` : "Run an eval compare to create the first CI report."}</p>
          </div>
          <div className="gate-rules">
            {gateFailures.length ? gateFailures.map((failure) => (
              <div className="gate-failure" key={failure.rule}>{failure.message}</div>
            )) : <div className="gate-pass-copy">Quality, cost, latency, and task completion are inside the configured release gate.</div>}
          </div>
          <div className="gate-metrics">
            <div><span>Regressed</span><strong>{fmtNum(gateSummary?.regressed_count)}</strong></div>
            <div><span>Failed</span><strong>{fmtNum(gateSummary?.run_b_failed_count)}</strong></div>
            <div><span>Not run</span><strong>{fmtNum(gateSummary?.run_b_not_run_count)}</strong></div>
            <div><span>Cost delta</span><strong>{gateSummary?.cost_delta_pct == null ? "n/a" : `${gateSummary.cost_delta_pct.toFixed(1)}%`}</strong></div>
            <div><span>Latency delta</span><strong>{gateSummary?.latency_delta_pct == null ? "n/a" : `${gateSummary.latency_delta_pct.toFixed(1)}%`}</strong></div>
          </div>
        </section>

        <section className="metric-grid">
          <MetricCard label="Health" value={health} detail={pct(errorRate)} tone={health === "Watch" ? "tone-danger" : "tone-good"} />
          <MetricCard label="Calls" value={fmtNum(summary.call_count)} detail={`${fmtNum(summary.trace_count)} traces`} />
          <MetricCard label="Cost" value={fmtMoney(summary.cost_usd)} detail={`${fmtNum(summary.total_tokens)} tokens`} />
          <MetricCard label="p95 latency" value={fmtMs(summary.p95_latency_ms)} detail={`avg ${fmtMs(summary.avg_latency_ms)}`} />
        </section>

        <section className="split-panel">
          <div className="chart-card">
            <div className="section-heading"><BarChart3 size={18} /> Cost and latency movement</div>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="cost" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#67e8f9" stopOpacity={0.55} />
                    <stop offset="100%" stopColor="#67e8f9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,.08)" vertical={false} />
                <XAxis dataKey="hour" tick={{ fill: "rgba(255,255,255,.55)", fontSize: 11 }} tickFormatter={(value) => String(value).slice(11, 16)} />
                <YAxis tick={{ fill: "rgba(255,255,255,.55)", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,.16)", borderRadius: 8 }} />
                <Area type="monotone" dataKey="avg_latency_ms" stroke="#fbbf24" fill="url(#cost)" strokeWidth={2} />
                <Area type="monotone" dataKey="call_count" stroke="#67e8f9" fill="transparent" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="alert-stack">
            <div className="section-heading"><AlertTriangle size={18} /> Live alert posture</div>
            {alerts.length ? alerts.map((alert) => (
              <article className={`alert-card ${alert.severity}`} key={alert.rule}>
                <strong>{alert.rule}</strong>
                <span>{alert.detail}</span>
              </article>
            )) : <div className="empty-state">No dynamic alert conditions in this window.</div>}
          </div>
        </section>

        <nav className="tabs">
          {[
            ["calls", "Calls", Activity],
            ["trace", "Trace", GitBranch],
            ["cost", "Cost", BarChart3],
            ["eval", "Eval", Layers],
          ].map(([id, label, Icon]) => (
            <button key={String(id)} className={activeTab === id ? "active" : ""} onClick={() => setActiveTab(String(id))}>
              <Icon size={16} /> {String(label)}
            </button>
          ))}
        </nav>

        {activeTab === "calls" ? (
          <section className="table-card">
            <div className="section-heading"><Search size={18} /> Recent call ledger</div>
            <div className="data-table">
              <table>
                <thead>
                  <tr><th>Status</th><th>Model</th><th>Tenant</th><th>Trace</th><th>Latency</th><th>Cost</th><th>Started</th></tr>
                </thead>
                <tbody>
                  {spans.map((span) => (
                    <tr key={span.span_id} onClick={() => { setDraftTraceId(span.trace_id); setState({ ...state, traceId: span.trace_id }); }}>
                      <td><span className={`status status-${span.status}`}>{span.status}</span></td>
                      <td>{span.model ?? "unknown"}</td>
                      <td>{span.tenant_id ?? "default"}</td>
                      <td><code>{span.trace_id}</code></td>
                      <td>{fmtMs(span.latency_ms)}</td>
                      <td>{fmtMoney(span.cost_usd)}</td>
                      <td>{span.started_at ? new Date(span.started_at).toLocaleString() : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}

        {activeTab === "trace" ? (
          <section className="table-card">
            <div className="section-heading"><GitBranch size={18} /> Trace inspection</div>
            {state.traceId ? <TraceTree spans={traceSpans} /> : <div className="empty-state">Select a row or paste a trace id to inspect the span tree.</div>}
          </section>
        ) : null}

        {activeTab === "cost" ? (
          <section className="table-card">
            <div className="section-heading"><BarChart3 size={18} /> Model economics</div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={models}>
                <CartesianGrid stroke="rgba(255,255,255,.08)" vertical={false} />
                <XAxis dataKey="model" tick={{ fill: "rgba(255,255,255,.55)", fontSize: 11 }} />
                <YAxis tick={{ fill: "rgba(255,255,255,.55)", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,.16)", borderRadius: 8 }} />
                <Bar dataKey="cost_usd" fill="#67e8f9" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </section>
        ) : null}

        {activeTab === "eval" ? (
          <section className="table-card">
            <div className="section-heading"><Layers size={18} /> Regression intelligence</div>
            <select className="report-select" value={selectedReport} onChange={(event) => setSelectedReport(event.target.value)}>
              {reports.map((report) => (
                <option key={report.report_id} value={report.report_id}>{report.task_set_name}: {report.run_id_b} vs {report.run_id_a}</option>
              ))}
            </select>
            <div className="data-table">
              <table>
                <thead><tr><th>Task</th><th>Run A</th><th>Run B</th><th>Score A</th><th>Score B</th><th>Regressed</th></tr></thead>
                <tbody>
                  {tasks.map((task) => (
                    <tr key={task.task_id}>
                      <td>{task.task_id}</td>
                      <td>{task.run_a_status}</td>
                      <td>{task.run_b_status}</td>
                      <td>{task.run_a_judge_score ?? ""}</td>
                      <td>{task.run_b_judge_score ?? ""}</td>
                      <td>{task.regressed ? "yes" : "no"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}
      </section>
    </main>
  );
}

export default App;

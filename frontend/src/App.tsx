import {
  Activity,
  AlertTriangle,
  BarChart3,
  Check,
  Clipboard,
  GitBranch,
  Layers,
  RefreshCcw,
  Search,
  Server,
  TerminalSquare,
} from "lucide-react";
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

const commands = [
  {
    id: "baseline",
    label: "1. Capture baseline",
    description: "Run the current agent version and tag its calls as the baseline.",
    command: "python example\\deepseek_agent_run.py --task-set agent_release_quality --run-id baseline --profile baseline",
  },
  {
    id: "candidate",
    label: "2. Capture candidate",
    description: "Run the changed agent version with the same task set.",
    command: "python example\\deepseek_agent_run.py --task-set agent_release_quality --run-id candidate --profile candidate",
  },
  {
    id: "compare",
    label: "3. Compare and gate",
    description: "Generate the release report that drives this screen.",
    command: "python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline",
  },
];

const fmtMoney = (value?: number | null) => `$${Number(value ?? 0).toFixed(4)}`;
const fmtMs = (value?: number | null) => `${Math.round(Number(value ?? 0)).toLocaleString()}ms`;
const fmtNum = (value?: number | null) => Math.round(Number(value ?? 0)).toLocaleString();
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
const fmtDelta = (value?: number | null) => (value == null ? "n/a" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`);

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

function CopyCommand({ command, copied, onCopy }: { command: string; copied: boolean; onCopy: () => void }) {
  return (
    <div className="command-row">
      <code>{command}</code>
      <button onClick={onCopy} type="button">
        {copied ? <Check size={15} /> : <Clipboard size={15} />}
        {copied ? "Copied" : "Copy command"}
      </button>
    </div>
  );
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

type ReleaseState = "failed" | "passed" | "no_gate" | "awaiting_candidate" | "no_report";

function releaseStateFor(report: EvalReport | undefined, summary: Summary): ReleaseState {
  if (!report) return summary.call_count > 0 ? "awaiting_candidate" : "no_report";
  const gate = report.summary?.gate;
  if (!gate || gate.configured === false) return "no_gate";
  return gate.status === "failed" ? "failed" : "passed";
}

function releaseCopy(state: ReleaseState, report: EvalReport | undefined) {
  if (state === "failed") {
    return {
      label: "FAILED",
      title: "Do not ship this candidate yet.",
      detail: "The candidate broke at least one configured regression gate. Open the failed tasks first, then inspect traces only where evidence is missing.",
    };
  }
  if (state === "passed") {
    return {
      label: "PASSED",
      title: "This candidate passed the release gate.",
      detail: "Quality, task completion, cost, and latency stayed inside the configured limits for this comparison.",
    };
  }
  if (state === "no_gate") {
    return {
      label: "NO GATE CONFIGURED",
      title: "This report is informational only.",
      detail: `${report?.task_set_name ?? "This task set"} produced a comparison, but it did not record configured gate rules. Add a gate block before treating this as a release decision.`,
    };
  }
  if (state === "awaiting_candidate") {
    return {
      label: "AWAITING CANDIDATE",
      title: "The gateway has data, but no release comparison exists yet.",
      detail: "Run a candidate with the same task set, then run compare. Until then, raw calls are only evidence, not a release verdict.",
    };
  }
  return {
    label: "NO REPORT",
    title: "Start with a baseline and candidate run.",
    detail: "Trajectory CI becomes useful after it can compare two agent versions. Copy the commands below and run them from the project root.",
  };
}

function App() {
  const buildLabel = "release-review-dashboard";
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
  const [activeTab, setActiveTab] = useState("tasks");
  const [draftTraceId, setDraftTraceId] = useState("");
  const [draftSessionId, setDraftSessionId] = useState("");
  const [copiedCommand, setCopiedCommand] = useState("");
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

  const copy = async (id: string, command: string) => {
    setCopiedCommand(id);
    window.setTimeout(() => setCopiedCommand(""), 1600);
    try {
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(command);
          return;
        } catch {
          // Fall back for browser automation, unfocused tabs, and older WebViews.
        }
      }
      const textarea = document.createElement("textarea");
      textarea.value = command;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    } catch {
      setError("Copy failed in this browser. Select the command text manually.");
    }
  };

  const selectedReportRecord = reports.find((report) => report.report_id === selectedReport) ?? reports[0];
  const gate = selectedReportRecord?.summary?.gate;
  const gateFailures = gate?.failures ?? [];
  const gateSummary = selectedReportRecord?.summary;
  const releaseState = releaseStateFor(selectedReportRecord, summary);
  const release = releaseCopy(releaseState, selectedReportRecord);
  const errorRate = summary.call_count ? summary.error_count / summary.call_count : 0;
  const failedTasks = tasks.filter((task) => task.regressed || task.run_b_status === "not_run" || task.run_b_status.includes("failed"));

  return (
    <main className="app-shell" data-build={buildLabel}>
      <aside className="sidebar">
        <div className="brand-lockup">
          <Server size={20} />
          <div>
            <strong>Trajectory CI</strong>
            <span>Agent release review</span>
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
          Call status
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
          <RefreshCcw size={16} /> Refresh data
        </button>
      </aside>

      <section className="content-shell release-shell">
        <section className="product-header">
          <div>
            <span className="eyebrow">Agent regression CI</span>
            <h1>Review an agent change like a release, not a metrics hunt.</h1>
            <p>Run a baseline, run a candidate, compare them, and use the gate result as the top-level shipping decision. Cost, latency, and traces explain the verdict.</p>
          </div>
          <div className="report-picker">
            <label>
              Current report
              <select value={selectedReport} onChange={(event) => setSelectedReport(event.target.value)} disabled={!reports.length}>
                {reports.length ? reports.map((report) => (
                  <option key={report.report_id} value={report.report_id}>{report.task_set_name}: {report.run_id_b} vs {report.run_id_a}</option>
                )) : <option value="">no reports yet</option>}
              </select>
            </label>
            <small>Default view shows the latest comparison. Older reports stay selectable for review.</small>
          </div>
        </section>

        {error ? <div className="error-banner">{error}</div> : null}

        <section className={`release-verdict release-${releaseState}`}>
          <div className="verdict-main">
            <span className="gate-kicker">Release decision</span>
            <h2>{release.label}</h2>
            <h3>{release.title}</h3>
            <p>{release.detail}</p>
          </div>
          <div className="verdict-reasons">
            <span>What to look at first</span>
            {gateFailures.length ? gateFailures.map((failure) => (
              <div className="gate-failure" key={failure.rule}>{failure.message}</div>
            )) : failedTasks.length ? failedTasks.slice(0, 3).map((task) => (
              <div className="gate-failure" key={task.task_id}>{task.task_id}: {task.detail?.diff?.reason ?? task.run_b_status}</div>
            )) : <div className="gate-pass-copy">No blocking task regression is selected. Use the workflow below if this screen has no comparison yet.</div>}
          </div>
          <div className="evidence-grid">
            <div><span>Regressed</span><strong>{fmtNum(gateSummary?.regressed_count)}</strong></div>
            <div><span>Candidate failed</span><strong>{fmtNum(gateSummary?.run_b_failed_count)}</strong></div>
            <div><span>Not run</span><strong>{fmtNum(gateSummary?.run_b_not_run_count)}</strong></div>
            <div><span>Cost impact</span><strong>{fmtDelta(gateSummary?.cost_delta_pct)}</strong></div>
            <div><span>Latency impact</span><strong>{fmtDelta(gateSummary?.latency_delta_pct)}</strong></div>
          </div>
        </section>

        <section className="workflow-panel">
          <div className="workflow-copy">
            <span className="eyebrow">Start here</span>
            <h2>Use it in three terminal commands.</h2>
            <p>The dashboard does not run your agent for you. It watches calls that your agent sends through the gateway, then turns a baseline-vs-candidate comparison into a release verdict.</p>
          </div>
          <div className="workflow-steps">
            {commands.map((item) => (
              <article className="workflow-step" key={item.id}>
                <div>
                  <strong>{item.label}</strong>
                  <p>{item.description}</p>
                </div>
                <CopyCommand command={item.command} copied={copiedCommand === item.id} onCopy={() => void copy(item.id, item.command)} />
              </article>
            ))}
          </div>
        </section>

        <nav className="tabs release-tabs">
          {[
            ["tasks", "Tasks", Layers],
            ["trace", "Traces", GitBranch],
            ["gateway", "Gateway Activity", Activity],
          ].map(([id, label, Icon]) => (
            <button key={String(id)} className={activeTab === id ? "active" : ""} onClick={() => setActiveTab(String(id))}>
              <Icon size={16} /> {String(label)}
            </button>
          ))}
        </nav>

        {activeTab === "tasks" ? (
          <section className="table-card">
            <div className="section-heading"><Layers size={18} /> Task-level release evidence</div>
            {selectedReportRecord ? (
              <div className="data-table">
                <table>
                  <thead><tr><th>Task</th><th>Baseline</th><th>Candidate</th><th>Score</th><th>Decision reason</th><th>Trace links</th></tr></thead>
                  <tbody>
                    {tasks.map((task) => (
                      <tr key={task.task_id}>
                        <td>{task.task_id}</td>
                        <td>{task.run_a_status}</td>
                        <td><span className={task.regressed ? "inline-danger" : ""}>{task.run_b_status}</span></td>
                        <td>{task.run_a_judge_score ?? "n/a"} &rarr; {task.run_b_judge_score ?? "n/a"}</td>
                        <td>{task.detail?.diff?.reason ?? (task.regressed ? "Candidate regressed" : "No regression detected")}</td>
                        <td>{[...(task.detail?.run_a?.trace_ids ?? []), ...(task.detail?.run_b?.trace_ids ?? [])].slice(0, 2).map((traceId: string) => <button className="trace-link" key={traceId} onClick={() => { setDraftTraceId(traceId); setState({ ...state, traceId }); setActiveTab("trace"); }}>{traceId.slice(0, 8)}</button>)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="empty-state">No release report yet. Copy the three commands above to create the first comparison.</div>}
          </section>
        ) : null}

        {activeTab === "trace" ? (
          <section className="table-card">
            <div className="section-heading"><GitBranch size={18} /> Trace inspection</div>
            {state.traceId ? <TraceTree spans={traceSpans} /> : <div className="empty-state">Select a task trace or paste a trace id in the sidebar. Traces are evidence for explaining a release verdict, not the first place to start.</div>}
          </section>
        ) : null}

        {activeTab === "gateway" ? (
          <section className="gateway-panel">
            <section className="metric-grid">
              <MetricCard label="Gateway health" value={errorRate > 0.2 ? "Watch" : "Nominal"} detail={`${pct(errorRate)} error rate`} tone={errorRate > 0.2 ? "tone-danger" : "tone-good"} />
              <MetricCard label="Raw calls" value={fmtNum(summary.call_count)} detail={`${fmtNum(summary.trace_count)} traces`} />
              <MetricCard label="Observed cost" value={fmtMoney(summary.cost_usd)} detail={`${fmtNum(summary.total_tokens)} tokens`} />
              <MetricCard label="p95 latency" value={fmtMs(summary.p95_latency_ms)} detail={`avg ${fmtMs(summary.avg_latency_ms)}`} />
            </section>

            <section className="split-panel">
              <div className="chart-card">
                <div className="section-heading"><BarChart3 size={18} /> Cost and latency evidence</div>
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
                <div className="section-heading"><AlertTriangle size={18} /> Runtime alerts</div>
                {alerts.length ? alerts.map((alert) => (
                  <article className={`alert-card ${alert.severity}`} key={alert.rule}>
                    <strong>{alert.rule}</strong>
                    <span>{alert.detail}</span>
                  </article>
                )) : <div className="empty-state">No dynamic alert conditions in this window.</div>}
              </div>
            </section>

            <section className="split-panel gateway-lower">
              <div className="table-card">
                <div className="section-heading"><Search size={18} /> Raw call ledger</div>
                <div className="data-table">
                  <table>
                    <thead>
                      <tr><th>Status</th><th>Model</th><th>Tenant</th><th>Trace</th><th>Latency</th><th>Cost</th><th>Started</th></tr>
                    </thead>
                    <tbody>
                      {spans.map((span) => (
                        <tr key={span.span_id} onClick={() => { setDraftTraceId(span.trace_id); setState({ ...state, traceId: span.trace_id }); setActiveTab("trace"); }}>
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
              </div>
              <div className="table-card">
                <div className="section-heading"><TerminalSquare size={18} /> Model economics</div>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={models}>
                    <CartesianGrid stroke="rgba(255,255,255,.08)" vertical={false} />
                    <XAxis dataKey="model" tick={{ fill: "rgba(255,255,255,.55)", fontSize: 11 }} />
                    <YAxis tick={{ fill: "rgba(255,255,255,.55)", fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,.16)", borderRadius: 8 }} />
                    <Bar dataKey="cost_usd" fill="#67e8f9" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          </section>
        ) : null}
      </section>
    </main>
  );
}

export default App;

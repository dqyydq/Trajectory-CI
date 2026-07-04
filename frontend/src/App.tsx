import {
  Activity,
  AlertTriangle,
  BarChart3,
  Check,
  Clipboard,
  GitBranch,
  Layers,
  Languages,
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

const translations = {
  en: {
    agentReleaseReview: "Agent release review",
    timeWindow: "Time window",
    tenant: "Tenant",
    allTenants: "all tenants",
    model: "Model",
    allModels: "all models",
    callStatus: "Call status",
    allStatuses: "all statuses",
    traceId: "Trace id",
    traceUuid: "trace uuid",
    sessionId: "Session id",
    session: "session",
    refreshData: "Refresh data",
    eyebrow: "Agent regression CI",
    headline: "Review an agent change like a release, not a metrics hunt.",
    intro: "Run a baseline, run a candidate, compare them, and use the gate result as the top-level shipping decision. Cost, latency, and traces explain the verdict.",
    currentReport: "Current report",
    noReportsYet: "no reports yet",
    reportHelp: "Default view shows the latest comparison. Older reports stay selectable for review.",
    releaseDecision: "Release decision",
    lookFirst: "What to look at first",
    noBlockingRegression: "No blocking task regression is selected. Use the workflow below if this screen has no comparison yet.",
    regressed: "Regressed",
    candidateFailed: "Candidate failed",
    notRun: "Not run",
    costImpact: "Cost impact",
    latencyImpact: "Latency impact",
    startHere: "Start here",
    workflowTitle: "Use it in three terminal commands.",
    workflowBody: "The dashboard does not run your agent for you. It watches calls that your agent sends through the gateway, then turns a baseline-vs-candidate comparison into a release verdict.",
    copied: "Copied",
    copyCommand: "Copy command",
    copyFailed: "Copy failed in this browser. Select the command text manually.",
    tabs: { tasks: "Tasks", trace: "Traces", gateway: "Gateway Activity" },
    taskEvidence: "Task-level release evidence",
    table: {
      task: "Task",
      baseline: "Baseline",
      candidate: "Candidate",
      score: "Score",
      decisionReason: "Decision reason",
      traceLinks: "Trace links",
      status: "Status",
      tenant: "Tenant",
      trace: "Trace",
      latency: "Latency",
      cost: "Cost",
      started: "Started",
    },
    noReleaseReport: "No release report yet. Copy the three commands above to create the first comparison.",
    candidateRegressed: "Candidate regressed",
    noRegressionDetected: "No regression detected",
    traceInspection: "Trace inspection",
    noSpansForTrace: "No spans found for this trace.",
    traceEmpty: "Select a task trace or paste a trace id in the sidebar. Traces are evidence for explaining a release verdict, not the first place to start.",
    request: "Request",
    response: "Response",
    open: "open",
    stream: "stream",
    sync: "sync",
    unknown: "unknown",
    gatewayHealth: "Gateway health",
    rawCalls: "Raw calls",
    observedCost: "Observed cost",
    p95Latency: "p95 latency",
    nominal: "Nominal",
    watch: "Watch",
    errorRate: "error rate",
    traces: "traces",
    tokens: "tokens",
    avg: "avg",
    costLatencyEvidence: "Cost and latency evidence",
    runtimeAlerts: "Runtime alerts",
    noAlerts: "No dynamic alert conditions in this window.",
    rawCallLedger: "Raw call ledger",
    modelEconomics: "Model economics",
    commands: {
      baselineLabel: "1. Capture baseline",
      baselineDescription: "Run the current agent version and tag its calls as the baseline.",
      candidateLabel: "2. Capture candidate",
      candidateDescription: "Run the changed agent version with the same task set.",
      compareLabel: "3. Compare and gate",
      compareDescription: "Generate the release report that drives this screen.",
    },
    release: {
      failed: {
        label: "FAILED",
        title: "Do not ship this candidate yet.",
        detail: "The candidate broke at least one configured regression gate. Open the failed tasks first, then inspect traces only where evidence is missing.",
      },
      passed: {
        label: "PASSED",
        title: "This candidate passed the release gate.",
        detail: "Quality, task completion, cost, and latency stayed inside the configured limits for this comparison.",
      },
      noGate: {
        label: "NO GATE CONFIGURED",
        title: "This report is informational only.",
        detail: "produced a comparison, but it did not record configured gate rules. Add a gate block before treating this as a release decision.",
      },
      awaitingCandidate: {
        label: "AWAITING CANDIDATE",
        title: "The gateway has data, but no release comparison exists yet.",
        detail: "Run a candidate with the same task set, then run compare. Until then, raw calls are only evidence, not a release verdict.",
      },
      noReport: {
        label: "NO REPORT",
        title: "Start with a baseline and candidate run.",
        detail: "Trajectory CI becomes useful after it can compare two agent versions. Copy the commands below and run them from the project root.",
      },
    },
  },
  zh: {
      "agentReleaseReview": "Agent 发版审查",
      "timeWindow": "时间窗口",
      "tenant": "租户",
      "allTenants": "全部租户",
      "model": "模型",
      "allModels": "全部模型",
      "callStatus": "调用状态",
      "allStatuses": "全部状态",
      "traceId": "Trace ID",
      "traceUuid": "trace uuid",
      "sessionId": "Session ID",
      "session": "session",
      "refreshData": "刷新数据",
      "eyebrow": "Agent 回归测试 CI",
      "headline": "像审查一次发版一样审查 Agent 改动。",
      "intro": "先跑 baseline，再跑 candidate，然后对比结果。页面最先给出能不能发版的 gate 判定，成本、延迟和 trace 只用于解释原因。",
      "currentReport": "当前报告",
      "noReportsYet": "暂无报告",
      "reportHelp": "默认展示最新对比结果。历史报告可以从这里切换查看。",
      "releaseDecision": "发版判定",
      "lookFirst": "优先看这里",
      "noBlockingRegression": "当前没有选中的阻塞回归。如果还没有对比报告，请先按下面流程运行。",
      "regressed": "回归任务",
      "candidateFailed": "Candidate 失败",
      "notRun": "未运行",
      "costImpact": "成本变化",
      "latencyImpact": "延迟变化",
      "startHere": "从这里开始",
      "workflowTitle": "三条命令跑完整流程。",
      "workflowBody": "看板不会替你运行 agent。你的 agent 通过网关发起调用后，系统会采集数据，再把 baseline 和 candidate 的对比结果转成发版判定。",
      "copied": "已复制",
      "copyCommand": "复制命令",
      "copyFailed": "当前浏览器复制失败，请手动选择命令文本。",
      "tabs": {
          "tasks": "任务结果",
          "trace": "Trace 证据",
          "gateway": "网关活动"
      },
      "taskEvidence": "任务级发版证据",
      "table": {
          "task": "任务",
          "baseline": "Baseline",
          "candidate": "Candidate",
          "score": "评分",
          "decisionReason": "判定原因",
          "traceLinks": "Trace 链接",
          "status": "状态",
          "tenant": "租户",
          "trace": "Trace",
          "latency": "延迟",
          "cost": "成本",
          "started": "开始时间"
      },
      "noReleaseReport": "还没有发版对比报告。复制上面的三条命令创建第一次对比。",
      "candidateRegressed": "Candidate 发生回归",
      "noRegressionDetected": "未发现回归",
      "traceInspection": "Trace 检查",
      "noSpansForTrace": "这个 trace 下没有找到 span。",
      "traceEmpty": "选择某个任务 trace，或在左侧粘贴 trace id。Trace 是解释发版判定的证据，不是新手第一入口。",
      "request": "请求",
      "response": "响应",
      "open": "进行中",
      "stream": "流式",
      "sync": "同步",
      "unknown": "未知",
      "gatewayHealth": "网关健康",
      "rawCalls": "原始调用",
      "observedCost": "观测成本",
      "p95Latency": "p95 延迟",
      "nominal": "正常",
      "watch": "需关注",
      "errorRate": "错误率",
      "traces": "traces",
      "tokens": "tokens",
      "avg": "平均",
      "costLatencyEvidence": "成本与延迟证据",
      "runtimeAlerts": "运行时告警",
      "noAlerts": "当前时间窗口没有动态告警。",
      "rawCallLedger": "原始调用记录",
      "modelEconomics": "模型成本分析",
      "commands": {
          "baselineLabel": "1. 采集 baseline",
          "baselineDescription": "运行当前版本 agent，并把调用标记为 baseline。",
          "candidateLabel": "2. 采集 candidate",
          "candidateDescription": "用同一组任务运行改动后的 agent。",
          "compareLabel": "3. 对比并执行 gate",
          "compareDescription": "生成驱动这个页面的发版审查报告。"
      },
      "release": {
          "failed": {
              "label": "不建议发版",
              "title": "这个 candidate 现在不应该上线。",
              "detail": "它触发了至少一条回归 gate。先看失败任务，再在证据不足时进入 trace。"
          },
          "passed": {
              "label": "可以发版",
              "title": "这个 candidate 通过了发版 gate。",
              "detail": "质量、任务完成情况、成本和延迟都在当前配置的阈值内。"
          },
          "noGate": {
              "label": "未配置 GATE",
              "title": "这份报告只能作为参考。",
              "detail": "生成了对比结果，但没有记录 gate 规则。请先在 task set 里加 gate 配置，再把它当作发版判定。"
          },
          "awaitingCandidate": {
              "label": "等待 Candidate",
              "title": "网关已有数据，但还没有发版对比报告。",
              "detail": "继续运行 candidate，再执行 compare。在此之前，原始调用只能算证据，不能算发版结论。"
          },
          "noReport": {
              "label": "暂无报告",
              "title": "先运行 baseline 和 candidate。",
              "detail": "Trajectory CI 只有在比较两个 agent 版本后才真正有价值。复制下面命令，在项目根目录执行。"
          }
      }
  },
};

type Language = keyof typeof translations;
type Copy = typeof translations.en;

function initialLanguage(): Language {
  const saved = window.localStorage.getItem("trajectory-ci-language");
  if (saved === "en" || saved === "zh") return saved;
  return window.navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function commandList(text: Copy) {
  return [
    {
      id: "baseline",
      label: text.commands.baselineLabel,
      description: text.commands.baselineDescription,
      command: "python example\\deepseek_agent_run.py --task-set agent_release_quality --run-id baseline --profile baseline",
    },
    {
      id: "candidate",
      label: text.commands.candidateLabel,
      description: text.commands.candidateDescription,
      command: "python example\\deepseek_agent_run.py --task-set agent_release_quality --run-id candidate --profile candidate",
    },
    {
      id: "compare",
      label: text.commands.compareLabel,
      description: text.commands.compareDescription,
      command: "python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline",
    },
  ];
}

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

function CopyCommand({ command, copied, onCopy, text }: { command: string; copied: boolean; onCopy: () => void; text: Copy }) {
  return (
    <div className="command-row">
      <code>{command}</code>
      <button onClick={onCopy} type="button">
        {copied ? <Check size={15} /> : <Clipboard size={15} />}
        {copied ? text.copied : text.copyCommand}
      </button>
    </div>
  );
}

function TraceTree({ spans, text }: { spans: SpanRecord[]; text: Copy }) {
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

  if (!rows.length) return <div className="empty-state">{text.noSpansForTrace}</div>;

  return (
    <div className="trace-tree">
      {rows.map(({ depth, span }) => (
        <details className="trace-node" key={span.span_id} style={{ marginLeft: depth * 18 }}>
          <summary>
            <code>{span.span_id}</code>
            <span className={`status status-${span.status}`}>{span.status}</span>
            <span>{span.span_type ?? "llm_call"}</span>
            <span>{span.model ?? text.unknown}</span>
            <span>{span.is_stream ? text.stream : text.sync}</span>
            <span>{span.ended_at ? fmtMs(span.latency_ms) : text.open}</span>
            <span>{fmtMoney(span.cost_usd)}</span>
          </summary>
          <div className="payload-grid">
            <div>
              <h4>{text.request}</h4>
              <JsonBlock value={span.request_body} />
            </div>
            <div>
              <h4>{text.response}</h4>
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

function releaseCopy(state: ReleaseState, report: EvalReport | undefined, text: Copy) {
  if (state === "failed") return text.release.failed;
  if (state === "passed") return text.release.passed;
  if (state === "no_gate") {
    return {
      ...text.release.noGate,
      detail: `${report?.task_set_name ?? "Task set"} ${text.release.noGate.detail}`,
    };
  }
  if (state === "awaiting_candidate") return text.release.awaitingCandidate;
  return text.release.noReport;
}

function App() {
  const buildLabel = "release-review-dashboard";
  const [language, setLanguage] = useState<Language>(initialLanguage);
  const text = translations[language];
  const commands = useMemo(() => commandList(text), [text]);
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
    window.localStorage.setItem("trajectory-ci-language", language);
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  }, [language]);

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
      setError(text.copyFailed);
    }
  };

  const selectedReportRecord = reports.find((report) => report.report_id === selectedReport) ?? reports[0];
  const gate = selectedReportRecord?.summary?.gate;
  const gateFailures = gate?.failures ?? [];
  const gateSummary = selectedReportRecord?.summary;
  const releaseState = releaseStateFor(selectedReportRecord, summary);
  const release = releaseCopy(releaseState, selectedReportRecord, text);
  const errorRate = summary.call_count ? summary.error_count / summary.call_count : 0;
  const failedTasks = tasks.filter((task) => task.regressed || task.run_b_status === "not_run" || task.run_b_status.includes("failed"));

  return (
    <main className="app-shell" data-build={buildLabel}>
      <aside className="sidebar">
        <div className="brand-lockup">
          <Server size={20} />
          <div>
            <strong>Trajectory CI</strong>
            <span>{text.agentReleaseReview}</span>
          </div>
        </div>

        <label>
          {text.timeWindow}
          <select value={state.hours} onChange={(event) => setState({ ...state, hours: Number(event.target.value) })}>
            {[1, 6, 12, 24, 72, 168].map((hours) => (
              <option key={hours} value={hours}>{hours}h</option>
            ))}
          </select>
        </label>
        <label>
          {text.tenant}
          <select value={state.tenantId} onChange={(event) => setState({ ...state, tenantId: event.target.value })}>
            <option value="">{text.allTenants}</option>
            {filters.tenants.map((tenant) => <option key={tenant} value={tenant}>{tenant}</option>)}
          </select>
        </label>
        <label>
          {text.model}
          <select value={state.model} onChange={(event) => setState({ ...state, model: event.target.value })}>
            <option value="">{text.allModels}</option>
            {filters.models.map((model) => <option key={model} value={model}>{model}</option>)}
          </select>
        </label>
        <label>
          {text.callStatus}
          <select value={state.status} onChange={(event) => setState({ ...state, status: event.target.value })}>
            <option value="">{text.allStatuses}</option>
            <option value="in_progress">in_progress</option>
            <option value="success">success</option>
            <option value="error">error</option>
          </select>
        </label>
        <label>
          {text.traceId}
          <input value={draftTraceId} onChange={(event) => setDraftTraceId(event.target.value)} placeholder={text.traceUuid} />
        </label>
        <label>
          {text.sessionId}
          <input value={draftSessionId} onChange={(event) => setDraftSessionId(event.target.value)} placeholder={text.session} />
        </label>
        <button className="refresh-button" onClick={applyFilters} disabled={loading}>
          <RefreshCcw size={16} /> {text.refreshData}
        </button>
      </aside>

      <section className="content-shell release-shell">
        <section className="product-header">
          <div>
            <span className="eyebrow">{text.eyebrow}</span>
            <h1>{text.headline}</h1>
            <p>{text.intro}</p>
          </div>
          <div className="header-actions">
            <button className="language-toggle" type="button" onClick={() => setLanguage(language === "zh" ? "en" : "zh")} aria-label="Switch language">
              <Languages size={16} />
              <span>{language === "zh" ? "EN" : "中文"}</span>
            </button>
            <div className="report-picker">
              <label>
              {text.currentReport}
              <select value={selectedReport} onChange={(event) => setSelectedReport(event.target.value)} disabled={!reports.length}>
                {reports.length ? reports.map((report) => (
                  <option key={report.report_id} value={report.report_id}>{report.task_set_name}: {report.run_id_b} vs {report.run_id_a}</option>
                )) : <option value="">{text.noReportsYet}</option>}
              </select>
              </label>
              <small>{text.reportHelp}</small>
            </div>
          </div>
        </section>

        {error ? <div className="error-banner">{error}</div> : null}

        <section className={`release-verdict release-${releaseState}`}>
          <div className="verdict-main">
            <span className="gate-kicker">{text.releaseDecision}</span>
            <h2>{release.label}</h2>
            <h3>{release.title}</h3>
            <p>{release.detail}</p>
          </div>
          <div className="verdict-reasons">
            <span>{text.lookFirst}</span>
            {gateFailures.length ? gateFailures.map((failure) => (
              <div className="gate-failure" key={failure.rule}>{failure.message}</div>
            )) : failedTasks.length ? failedTasks.slice(0, 3).map((task) => (
              <div className="gate-failure" key={task.task_id}>{task.task_id}: {task.detail?.diff?.reason ?? task.run_b_status}</div>
            )) : <div className="gate-pass-copy">{text.noBlockingRegression}</div>}
          </div>
          <div className="evidence-grid">
            <div><span>{text.regressed}</span><strong>{fmtNum(gateSummary?.regressed_count)}</strong></div>
            <div><span>{text.candidateFailed}</span><strong>{fmtNum(gateSummary?.run_b_failed_count)}</strong></div>
            <div><span>{text.notRun}</span><strong>{fmtNum(gateSummary?.run_b_not_run_count)}</strong></div>
            <div><span>{text.costImpact}</span><strong>{fmtDelta(gateSummary?.cost_delta_pct)}</strong></div>
            <div><span>{text.latencyImpact}</span><strong>{fmtDelta(gateSummary?.latency_delta_pct)}</strong></div>
          </div>
        </section>

        <section className="workflow-panel">
          <div className="workflow-copy">
            <span className="eyebrow">{text.startHere}</span>
            <h2>{text.workflowTitle}</h2>
            <p>{text.workflowBody}</p>
          </div>
          <div className="workflow-steps">
            {commands.map((item) => (
              <article className="workflow-step" key={item.id}>
                <div>
                  <strong>{item.label}</strong>
                  <p>{item.description}</p>
                </div>
                <CopyCommand command={item.command} copied={copiedCommand === item.id} onCopy={() => void copy(item.id, item.command)} text={text} />
              </article>
            ))}
          </div>
        </section>

        <nav className="tabs release-tabs">
          {[
            ["tasks", text.tabs.tasks, Layers],
            ["trace", text.tabs.trace, GitBranch],
            ["gateway", text.tabs.gateway, Activity],
          ].map(([id, label, Icon]) => (
            <button key={String(id)} className={activeTab === id ? "active" : ""} onClick={() => setActiveTab(String(id))}>
              <Icon size={16} /> {String(label)}
            </button>
          ))}
        </nav>

        {activeTab === "tasks" ? (
          <section className="table-card">
            <div className="section-heading"><Layers size={18} /> {text.taskEvidence}</div>
            {selectedReportRecord ? (
              <div className="data-table">
                <table>
                  <thead><tr><th>{text.table.task}</th><th>{text.table.baseline}</th><th>{text.table.candidate}</th><th>{text.table.score}</th><th>{text.table.decisionReason}</th><th>{text.table.traceLinks}</th></tr></thead>
                  <tbody>
                    {tasks.map((task) => (
                      <tr key={task.task_id}>
                        <td>{task.task_id}</td>
                        <td>{task.run_a_status}</td>
                        <td><span className={task.regressed ? "inline-danger" : ""}>{task.run_b_status}</span></td>
                        <td>{task.run_a_judge_score ?? "n/a"} &rarr; {task.run_b_judge_score ?? "n/a"}</td>
                        <td>{task.detail?.diff?.reason ?? (task.regressed ? text.candidateRegressed : text.noRegressionDetected)}</td>
                        <td>{[...(task.detail?.run_a?.trace_ids ?? []), ...(task.detail?.run_b?.trace_ids ?? [])].slice(0, 2).map((traceId: string) => <button className="trace-link" key={traceId} onClick={() => { setDraftTraceId(traceId); setState({ ...state, traceId }); setActiveTab("trace"); }}>{traceId.slice(0, 8)}</button>)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="empty-state">{text.noReleaseReport}</div>}
          </section>
        ) : null}

        {activeTab === "trace" ? (
          <section className="table-card">
            <div className="section-heading"><GitBranch size={18} /> {text.traceInspection}</div>
            {state.traceId ? <TraceTree spans={traceSpans} text={text} /> : <div className="empty-state">{text.traceEmpty}</div>}
          </section>
        ) : null}

        {activeTab === "gateway" ? (
          <section className="gateway-panel">
            <section className="metric-grid">
              <MetricCard label={text.gatewayHealth} value={errorRate > 0.2 ? text.watch : text.nominal} detail={`${pct(errorRate)} ${text.errorRate}`} tone={errorRate > 0.2 ? "tone-danger" : "tone-good"} />
              <MetricCard label={text.rawCalls} value={fmtNum(summary.call_count)} detail={`${fmtNum(summary.trace_count)} ${text.traces}`} />
              <MetricCard label={text.observedCost} value={fmtMoney(summary.cost_usd)} detail={`${fmtNum(summary.total_tokens)} ${text.tokens}`} />
              <MetricCard label={text.p95Latency} value={fmtMs(summary.p95_latency_ms)} detail={`${text.avg} ${fmtMs(summary.avg_latency_ms)}`} />
            </section>

            <section className="split-panel">
              <div className="chart-card">
                <div className="section-heading"><BarChart3 size={18} /> {text.costLatencyEvidence}</div>
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
                <div className="section-heading"><AlertTriangle size={18} /> {text.runtimeAlerts}</div>
                {alerts.length ? alerts.map((alert) => (
                  <article className={`alert-card ${alert.severity}`} key={alert.rule}>
                    <strong>{alert.rule}</strong>
                    <span>{alert.detail}</span>
                  </article>
                )) : <div className="empty-state">{text.noAlerts}</div>}
              </div>
            </section>

            <section className="split-panel gateway-lower">
              <div className="table-card">
                <div className="section-heading"><Search size={18} /> {text.rawCallLedger}</div>
                <div className="data-table">
                  <table>
                    <thead>
                      <tr><th>{text.table.status}</th><th>{text.model}</th><th>{text.table.tenant}</th><th>{text.table.trace}</th><th>{text.table.latency}</th><th>{text.table.cost}</th><th>{text.table.started}</th></tr>
                    </thead>
                    <tbody>
                      {spans.map((span) => (
                        <tr key={span.span_id} onClick={() => { setDraftTraceId(span.trace_id); setState({ ...state, traceId: span.trace_id }); setActiveTab("trace"); }}>
                          <td><span className={`status status-${span.status}`}>{span.status}</span></td>
                          <td>{span.model ?? text.unknown}</td>
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
                <div className="section-heading"><TerminalSquare size={18} /> {text.modelEconomics}</div>
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

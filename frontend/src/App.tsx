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
  "en": {
    "agentReleaseReview": "Agent release review",
    "timeWindow": "Time window",
    "tenant": "Tenant",
    "allTenants": "all tenants",
    "model": "Model",
    "allModels": "all models",
    "callStatus": "Call status",
    "allStatuses": "all statuses",
    "traceId": "Trace id",
    "traceUuid": "trace uuid",
    "sessionId": "Session id",
    "session": "session",
    "refreshData": "Refresh data",
    "eyebrow": "Agent regression CI",
    "headline": "Know whether an agent change is safe to ship.",
    "intro": "Capture a baseline, capture a candidate, compare them, and read the release gate first. Cost, latency, and traces are evidence for the verdict.",
    "currentReport": "Current report",
    "noReportsYet": "no reports yet",
    "reportHelp": "Default view shows the latest comparison. Older reports stay selectable for review.",
    "releaseDecision": "Release decision",
    "lookFirst": "What to look at first",
    "noBlockingRegression": "No blocking task regression is selected. If this screen has no comparison yet, start with the workflow below.",
    "regressed": "Regressed",
    "candidateFailed": "Candidate failed",
    "notRun": "Not run",
    "costImpact": "Cost impact",
    "latencyImpact": "Latency impact",
    "startHere": "Start here",
    "workflowTitle": "Run one release review in five steps.",
    "workflowBody": "The dashboard does not run your agent. Your agent sends calls through the gateway; Trajectory CI turns the baseline-vs-candidate evidence into a release verdict.",
    "lookingTitle": "What you are looking at",
    "lookingBody": "This is a candidate-vs-baseline release review. Read the gate first, inspect regressed tasks second, and use raw traces only when you need proof.",
    "rawEvidenceTitle": "Raw evidence, not the main workflow",
    "rawEvidenceBody": "Gateway Activity shows operational evidence collected while your agent ran. Use it to explain a release decision; do not start here unless you are debugging capture or provider behavior.",
    "copied": "Copied",
    "copyCommand": "Copy command",
    "copyFailed": "Copy failed in this browser. Select the command text manually.",
    "tabs": {
      "tasks": "Tasks",
      "trace": "Traces",
      "gateway": "Gateway Activity"
    },
    "taskEvidence": "Task-level release evidence",
    "table": {
      "task": "Task",
      "baseline": "Baseline",
      "candidate": "Candidate",
      "score": "Score",
      "decisionReason": "Decision reason",
      "traceLinks": "Trace links",
      "status": "Status",
      "tenant": "Tenant",
      "trace": "Trace",
      "latency": "Latency",
      "cost": "Cost",
      "started": "Started"
    },
    "noReleaseReport": "No release report yet. Copy the workflow commands above to create the first comparison.",
    "candidateRegressed": "Candidate regressed",
    "noRegressionDetected": "No regression detected",
    "traceInspection": "Trace inspection",
    "noSpansForTrace": "No spans found for this trace.",
    "traceEmpty": "Select a task trace or paste a trace id in the sidebar. Traces are evidence for explaining a release verdict, not the first place to start.",
    "request": "Request",
    "response": "Response",
    "open": "open",
    "stream": "stream",
    "sync": "sync",
    "unknown": "unknown",
    "gatewayHealth": "Gateway health",
    "rawCalls": "Raw calls",
    "observedCost": "Observed cost",
    "p95Latency": "p95 latency",
    "nominal": "Nominal",
    "watch": "Watch",
    "errorRate": "error rate",
    "traces": "traces",
    "tokens": "tokens",
    "avg": "avg",
    "costLatencyEvidence": "Cost and latency evidence",
    "runtimeAlerts": "Runtime alerts",
    "noAlerts": "No dynamic alert conditions in this window.",
    "rawCallLedger": "Raw call ledger",
    "modelEconomics": "Model economics",
    "commands": {
      "startLabel": "1. Start services",
      "startDescription": "Start Postgres, apply migrations, then run the FastAPI gateway and React dashboard.",
      "baselineLabel": "2. Capture baseline",
      "baselineDescription": "Run the current agent version and tag its calls as the baseline.",
      "candidateLabel": "3. Capture candidate",
      "candidateDescription": "Run the changed agent version with the same task set.",
      "compareLabel": "4. Compare and gate",
      "compareDescription": "Generate the release report that drives this screen.",
      "openLabel": "5. Open dashboard",
      "openDescription": "Read the release verdict first, then inspect task diffs and trace evidence."
    },
    "release": {
      "failed": {
        "label": "FAILED",
        "title": "Do not ship this candidate yet.",
        "detail": "The candidate broke at least one configured regression gate. Open the failed tasks first, then inspect traces only where evidence is missing."
      },
      "passed": {
        "label": "PASSED",
        "title": "This candidate passed the release gate.",
        "detail": "Quality, task completion, cost, and latency stayed inside the configured limits for this comparison."
      },
      "noGate": {
        "label": "NO GATE CONFIGURED",
        "title": "This report is informational only.",
        "detail": "produced a comparison, but it did not record configured gate rules. Add a gate block before treating this as a release decision."
      },
      "awaitingCandidate": {
        "label": "AWAITING CANDIDATE",
        "title": "The gateway has data, but no release comparison exists yet.",
        "detail": "Run a candidate with the same task set, then run compare. Until then, raw calls are only evidence, not a release verdict."
      },
      "noReport": {
        "label": "NO REPORT",
        "title": "Start with a baseline and candidate run.",
        "detail": "Trajectory CI becomes useful after it can compare two agent versions. Copy the commands below and run them from the project root."
      }
    }
  },
  "zh": {
    "agentReleaseReview": "Agent \u53d1\u7248\u5ba1\u67e5",
    "timeWindow": "\u65f6\u95f4\u7a97\u53e3",
    "tenant": "\u79df\u6237",
    "allTenants": "\u5168\u90e8\u79df\u6237",
    "model": "\u6a21\u578b",
    "allModels": "\u5168\u90e8\u6a21\u578b",
    "callStatus": "\u8c03\u7528\u72b6\u6001",
    "allStatuses": "\u5168\u90e8\u72b6\u6001",
    "traceId": "Trace ID",
    "traceUuid": "trace uuid",
    "sessionId": "Session ID",
    "session": "session",
    "refreshData": "\u5237\u65b0\u6570\u636e",
    "eyebrow": "Agent \u56de\u5f52\u6d4b\u8bd5 CI",
    "headline": "\u5224\u65ad\u4e00\u6b21 Agent \u6539\u52a8\u80fd\u4e0d\u80fd\u53d1\u7248\u3002",
    "intro": "\u5148\u91c7\u96c6 baseline\uff0c\u518d\u91c7\u96c6 candidate\uff0c\u7136\u540e\u5bf9\u6bd4\u4e24\u6b21\u7ed3\u679c\u3002\u9875\u9762\u6700\u5148\u5c55\u793a\u53d1\u7248 gate\uff0c\u6210\u672c\u3001\u5ef6\u8fdf\u548c trace \u53ea\u662f\u89e3\u91ca\u8fd9\u4e2a\u7ed3\u8bba\u7684\u8bc1\u636e\u3002",
    "currentReport": "\u5f53\u524d\u62a5\u544a",
    "noReportsYet": "\u6682\u65e0\u62a5\u544a",
    "reportHelp": "\u9ed8\u8ba4\u5c55\u793a\u6700\u65b0\u5bf9\u6bd4\u7ed3\u679c\u3002\u5386\u53f2\u62a5\u544a\u53ef\u4ee5\u4ece\u8fd9\u91cc\u5207\u6362\u67e5\u770b\u3002",
    "releaseDecision": "\u53d1\u7248\u5224\u5b9a",
    "lookFirst": "\u4f18\u5148\u770b\u8fd9\u91cc",
    "noBlockingRegression": "\u5f53\u524d\u6ca1\u6709\u9009\u4e2d\u7684\u963b\u585e\u56de\u5f52\u3002\u5982\u679c\u8fd8\u6ca1\u6709\u5bf9\u6bd4\u62a5\u544a\uff0c\u8bf7\u5148\u6309\u4e0b\u9762\u6d41\u7a0b\u8fd0\u884c\u3002",
    "regressed": "\u56de\u5f52\u4efb\u52a1",
    "candidateFailed": "Candidate \u5931\u8d25",
    "notRun": "\u672a\u8fd0\u884c",
    "costImpact": "\u6210\u672c\u53d8\u5316",
    "latencyImpact": "\u5ef6\u8fdf\u53d8\u5316",
    "startHere": "\u4ece\u8fd9\u91cc\u5f00\u59cb",
    "workflowTitle": "\u4e94\u6b65\u5b8c\u6210\u4e00\u6b21\u53d1\u7248\u5ba1\u67e5\u3002",
    "workflowBody": "\u770b\u677f\u4e0d\u4f1a\u66ff\u4f60\u8fd0\u884c agent\u3002\u4f60\u7684 agent \u901a\u8fc7\u7f51\u5173\u53d1\u8d77\u8c03\u7528\uff0cTrajectory CI \u628a baseline \u548c candidate \u7684\u8bc1\u636e\u8f6c\u6210\u53d1\u7248\u7ed3\u8bba\u3002",
    "lookingTitle": "\u4f60\u6b63\u5728\u770b\u4ec0\u4e48",
    "lookingBody": "\u8fd9\u662f\u4e00\u6b21 candidate-vs-baseline \u53d1\u7248\u5ba1\u67e5\u3002\u5148\u770b gate\uff0c\u518d\u770b\u56de\u5f52\u4efb\u52a1\uff0c\u53ea\u6709\u9700\u8981\u8bc1\u636e\u65f6\u624d\u8fdb\u5165\u539f\u59cb trace\u3002",
    "rawEvidenceTitle": "\u539f\u59cb\u8bc1\u636e\uff0c\u4e0d\u662f\u4e3b\u6d41\u7a0b",
    "rawEvidenceBody": "Gateway Activity \u5c55\u793a agent \u8fd0\u884c\u65f6\u91c7\u96c6\u5230\u7684\u64cd\u4f5c\u8bc1\u636e\u3002\u7528\u5b83\u89e3\u91ca\u53d1\u7248\u5224\u5b9a\uff0c\u4e0d\u8981\u628a\u5b83\u5f53\u6210\u7b2c\u4e00\u5165\u53e3\u3002",
    "copied": "\u5df2\u590d\u5236",
    "copyCommand": "\u590d\u5236\u547d\u4ee4",
    "copyFailed": "\u5f53\u524d\u6d4f\u89c8\u5668\u590d\u5236\u5931\u8d25\uff0c\u8bf7\u624b\u52a8\u9009\u62e9\u547d\u4ee4\u6587\u672c\u3002",
    "tabs": {
      "tasks": "\u4efb\u52a1\u7ed3\u679c",
      "trace": "Trace \u8bc1\u636e",
      "gateway": "\u7f51\u5173\u6d3b\u52a8"
    },
    "taskEvidence": "\u4efb\u52a1\u7ea7\u53d1\u7248\u8bc1\u636e",
    "table": {
      "task": "\u4efb\u52a1",
      "baseline": "Baseline",
      "candidate": "Candidate",
      "score": "\u8bc4\u5206",
      "decisionReason": "\u5224\u5b9a\u539f\u56e0",
      "traceLinks": "Trace \u94fe\u63a5",
      "status": "\u72b6\u6001",
      "tenant": "\u79df\u6237",
      "trace": "Trace",
      "latency": "\u5ef6\u8fdf",
      "cost": "\u6210\u672c",
      "started": "\u5f00\u59cb\u65f6\u95f4"
    },
    "noReleaseReport": "\u8fd8\u6ca1\u6709\u53d1\u7248\u5bf9\u6bd4\u62a5\u544a\u3002\u590d\u5236\u4e0a\u9762\u7684\u6d41\u7a0b\u547d\u4ee4\u521b\u5efa\u7b2c\u4e00\u6b21\u5bf9\u6bd4\u3002",
    "candidateRegressed": "Candidate \u53d1\u751f\u56de\u5f52",
    "noRegressionDetected": "\u672a\u53d1\u73b0\u56de\u5f52",
    "traceInspection": "Trace \u68c0\u67e5",
    "noSpansForTrace": "\u8fd9\u4e2a trace \u4e0b\u6ca1\u6709\u627e\u5230 span\u3002",
    "traceEmpty": "\u9009\u62e9\u67d0\u4e2a\u4efb\u52a1 trace\uff0c\u6216\u5728\u5de6\u4fa7\u7c98\u8d34 trace id\u3002Trace \u662f\u89e3\u91ca\u53d1\u7248\u5224\u5b9a\u7684\u8bc1\u636e\uff0c\u4e0d\u662f\u65b0\u624b\u7b2c\u4e00\u5165\u53e3\u3002",
    "request": "\u8bf7\u6c42",
    "response": "\u54cd\u5e94",
    "open": "\u8fdb\u884c\u4e2d",
    "stream": "\u6d41\u5f0f",
    "sync": "\u540c\u6b65",
    "unknown": "\u672a\u77e5",
    "gatewayHealth": "\u7f51\u5173\u5065\u5eb7",
    "rawCalls": "\u539f\u59cb\u8c03\u7528",
    "observedCost": "\u89c2\u6d4b\u6210\u672c",
    "p95Latency": "p95 \u5ef6\u8fdf",
    "nominal": "\u6b63\u5e38",
    "watch": "\u9700\u5173\u6ce8",
    "errorRate": "\u9519\u8bef\u7387",
    "traces": "traces",
    "tokens": "tokens",
    "avg": "\u5e73\u5747",
    "costLatencyEvidence": "\u6210\u672c\u4e0e\u5ef6\u8fdf\u8bc1\u636e",
    "runtimeAlerts": "\u8fd0\u884c\u65f6\u544a\u8b66",
    "noAlerts": "\u5f53\u524d\u65f6\u95f4\u7a97\u53e3\u6ca1\u6709\u52a8\u6001\u544a\u8b66\u3002",
    "rawCallLedger": "\u539f\u59cb\u8c03\u7528\u8bb0\u5f55",
    "modelEconomics": "\u6a21\u578b\u6210\u672c\u5206\u6790",
    "commands": {
      "startLabel": "1. \u542f\u52a8\u670d\u52a1",
      "startDescription": "\u542f\u52a8 Postgres\uff0c\u6267\u884c\u8fc1\u79fb\uff0c\u7136\u540e\u542f\u52a8 FastAPI \u7f51\u5173\u548c React \u770b\u677f\u3002",
      "baselineLabel": "2. \u91c7\u96c6 baseline",
      "baselineDescription": "\u8fd0\u884c\u5f53\u524d\u7248\u672c agent\uff0c\u5e76\u628a\u8c03\u7528\u6807\u8bb0\u4e3a baseline\u3002",
      "candidateLabel": "3. \u91c7\u96c6 candidate",
      "candidateDescription": "\u7528\u540c\u4e00\u7ec4\u4efb\u52a1\u8fd0\u884c\u6539\u52a8\u540e\u7684 agent\u3002",
      "compareLabel": "4. \u5bf9\u6bd4\u5e76\u6267\u884c gate",
      "compareDescription": "\u751f\u6210\u9a71\u52a8\u8fd9\u4e2a\u9875\u9762\u7684\u53d1\u7248\u5ba1\u67e5\u62a5\u544a\u3002",
      "openLabel": "5. \u6253\u5f00\u770b\u677f",
      "openDescription": "\u5148\u770b\u53d1\u7248\u5224\u5b9a\uff0c\u518d\u770b\u4efb\u52a1 diff \u548c trace \u8bc1\u636e\u3002"
    },
    "release": {
      "failed": {
        "label": "\u4e0d\u5efa\u8bae\u53d1\u7248",
        "title": "\u8fd9\u4e2a candidate \u73b0\u5728\u4e0d\u5e94\u8be5\u4e0a\u7ebf\u3002",
        "detail": "\u5b83\u89e6\u53d1\u4e86\u81f3\u5c11\u4e00\u6761\u56de\u5f52 gate\u3002\u5148\u770b\u5931\u8d25\u4efb\u52a1\uff0c\u518d\u5728\u8bc1\u636e\u4e0d\u8db3\u65f6\u8fdb\u5165 trace\u3002"
      },
      "passed": {
        "label": "\u53ef\u4ee5\u53d1\u7248",
        "title": "\u8fd9\u4e2a candidate \u901a\u8fc7\u4e86\u53d1\u7248 gate\u3002",
        "detail": "\u8d28\u91cf\u3001\u4efb\u52a1\u5b8c\u6210\u60c5\u51b5\u3001\u6210\u672c\u548c\u5ef6\u8fdf\u90fd\u5728\u5f53\u524d\u914d\u7f6e\u7684\u9608\u503c\u5185\u3002"
      },
      "noGate": {
        "label": "\u672a\u914d\u7f6e GATE",
        "title": "\u8fd9\u4efd\u62a5\u544a\u53ea\u80fd\u4f5c\u4e3a\u53c2\u8003\u3002",
        "detail": "\u751f\u6210\u4e86\u5bf9\u6bd4\u7ed3\u679c\uff0c\u4f46\u6ca1\u6709\u8bb0\u5f55 gate \u89c4\u5219\u3002\u8bf7\u5148\u5728 task set \u91cc\u52a0 gate \u914d\u7f6e\uff0c\u518d\u628a\u5b83\u5f53\u4f5c\u53d1\u7248\u5224\u5b9a\u3002"
      },
      "awaitingCandidate": {
        "label": "\u7b49\u5f85 Candidate",
        "title": "\u7f51\u5173\u5df2\u6709\u6570\u636e\uff0c\u4f46\u8fd8\u6ca1\u6709\u53d1\u7248\u5bf9\u6bd4\u62a5\u544a\u3002",
        "detail": "\u7ee7\u7eed\u8fd0\u884c candidate\uff0c\u518d\u6267\u884c compare\u3002\u5728\u6b64\u4e4b\u524d\uff0c\u539f\u59cb\u8c03\u7528\u53ea\u80fd\u7b97\u8bc1\u636e\uff0c\u4e0d\u80fd\u7b97\u53d1\u7248\u7ed3\u8bba\u3002"
      },
      "noReport": {
        "label": "\u6682\u65e0\u62a5\u544a",
        "title": "\u5148\u8fd0\u884c baseline \u548c candidate\u3002",
        "detail": "Trajectory CI \u53ea\u6709\u5728\u6bd4\u8f83\u4e24\u4e2a agent \u7248\u672c\u540e\u624d\u771f\u6b63\u6709\u4ef7\u503c\u3002\u590d\u5236\u4e0b\u9762\u547d\u4ee4\uff0c\u5728\u9879\u76ee\u6839\u76ee\u5f55\u6267\u884c\u3002"
      }
    }
  }
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
      id: "start",
      label: text.commands.startLabel,
      description: text.commands.startDescription,
      command: String.raw`.venv\Scripts\activate; docker compose up -d; alembic upgrade head; uvicorn app.main:app --reload --port 8000`,
    },
    {
      id: "baseline",
      label: text.commands.baselineLabel,
      description: text.commands.baselineDescription,
      command: String.raw`python example\deepseek_agent_run.py --task-set agent_release_quality --run-id baseline --profile baseline`,
    },
    {
      id: "candidate",
      label: text.commands.candidateLabel,
      description: text.commands.candidateDescription,
      command: String.raw`python example\deepseek_agent_run.py --task-set agent_release_quality --run-id candidate --profile candidate`,
    },
    {
      id: "compare",
      label: text.commands.compareLabel,
      description: text.commands.compareDescription,
      command: "python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline",
    },
    {
      id: "open",
      label: text.commands.openLabel,
      description: text.commands.openDescription,
      command: "http://127.0.0.1:5173/dashboard/",
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

        <section className="context-panel">
          <span className="eyebrow">{text.lookingTitle}</span>
          <p>{text.lookingBody}</p>
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
            <section className="gateway-context">
              <span className="eyebrow">{text.rawEvidenceTitle}</span>
              <p>{text.rawEvidenceBody}</p>
            </section>
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

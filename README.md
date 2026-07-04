# Trajectory CI

Trajectory CI is an Agent Regression CI tool. It helps AI agent developers answer one release question:

> I changed a prompt, model, tool, or system instruction. Is this candidate safer to ship than the baseline?

Run your current agent as a **baseline**, run the changed agent as a **candidate**, then compare the two runs. The result is a CI-style release gate:

```text
REGRESSION GATE: PASSED
```

or:

```text
REGRESSION GATE: FAILED
- regressed tasks 1 exceeded allowed 0
```

Traces, cost, latency, judge reasons, and the dashboard are not the product by themselves. They are release evidence: they explain why a candidate passed or failed.

## Quickstart: Review One Agent Change

Prerequisites: Docker Desktop is running, `.env` contains your provider key, and dependencies are installed.

1. Start the local services:

```powershell
.venv\Scripts\activate
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

2. In another terminal, start the dashboard:

```powershell
cd frontend
npm install
npm run dev
```

3. Run the current agent as the baseline:

```powershell
.venv\Scripts\activate
python example\deepseek_agent_run.py --task-set agent_release_quality --run-id baseline --profile baseline
```

4. Run the changed agent as the candidate:

```powershell
python example\deepseek_agent_run.py --task-set agent_release_quality --run-id candidate --profile candidate
```

5. Compare the two runs:

```powershell
python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline
```

Open the release review dashboard at `http://127.0.0.1:5173/dashboard/`.

The first thing to read is the release decision. If it fails, the task table, judge reasons, cost/latency deltas, and trace links explain why.

## What Problem This Solves

Agent changes are hard to review manually. A shorter prompt can reduce cost but remove critical caveats. A model swap can improve latency but break tool usage. A tool change can pass a smoke test while regressing a specific workflow.

Trajectory CI gives that review a repeatable shape:

- Define a task set your agent must keep passing.
- Capture a baseline run and a candidate run through the local gateway.
- Compare task outcomes, judge scores, trace IDs, cost, and latency.
- Apply a regression gate so the result is red or green.
- Drill into traces only when you need evidence.

## Why Not Just Use A Trace Tool?

| Tool type | Primary question | Typical output |
| --- | --- | --- |
| Langfuse / Helicone / Phoenix | What happened in this LLM call or trace? | Logs, traces, scores, dashboards |
| Trajectory CI | Can this agent change ship? | Baseline-vs-candidate release gate with task diffs and evidence |

Trajectory CI is not trying to beat mature tracing products at tracing. It uses tracing as the data layer for regression review.

## Case Study: Cheaper Prompt, Failed Gate

The included DeepSeek-backed case compares two prompt profiles on the same agent tasks:

- `baseline`: concise but complete engineering answers with caveats and tradeoffs.
- `candidate`: aggressively shorter answers intended to reduce token usage and latency.

The candidate looked attractive on infrastructure metrics:

- Cost dropped from `$0.000579` to `$0.000188` (`-67.5%`).
- Average latency dropped from `10445ms` to `3646ms` (`-65.1%`).

But the release gate failed because the candidate omitted important debugging evidence in `failed_agent_investigation`:

```text
REGRESSION GATE: FAILED
- regressed tasks 1 exceeded allowed 0
```

Read the generated report at [`docs/reports/agent-release-quality.md`](docs/reports/agent-release-quality.md).

## How It Works With Your Own Agent

Your agent keeps using an OpenAI-compatible or Anthropic-compatible client. Point the client at the local gateway and tag each evaluation call.

For OpenAI-compatible clients, change only the base URL and add evaluation headers:

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-provider-key",
    base_url="http://127.0.0.1:8000/v1",
)

response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "Should we ship this candidate?"}],
    extra_headers={
        "X-Eval-Task-Id": "release_tradeoff",
        "X-Eval-Run-Id": "candidate",
        "X-Session-Id": "agent_release_quality:release_tradeoff:candidate",
    },
)
```

The gateway forwards the request to the real provider, records the trace evidence, and keeps the provider credential out of the database.

## Task Sets And Release Gates

A task set defines what the agent must keep doing correctly and what counts as a failed release gate:

```yaml
gate:
  max_regressed_tasks: 0
  max_failed_tasks: 0
  max_not_run_tasks: 0
  max_cost_increase_pct: 15
  max_latency_increase_pct: 20

tasks:
  - task_id: "agent_release_tradeoff"
    description: "The agent should explain whether a cheaper candidate is safe to ship."
    input: "A cheaper model reduces cost but lowers answer quality. Should we ship it?"
    judge_rubric: "Reward answers that weigh quality, cost, latency, and regression risk."
```

Run a baseline and candidate through your agent, then compare:

```powershell
python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline
```

The compare command exits non-zero when the gate fails. Use `--no-fail-on-gate` when you want to inspect a failed report locally without failing the shell step.

Export a markdown report:

```powershell
python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline --export-markdown report.md
```

## Dashboard

The React dashboard is a release review surface, not a generic monitoring board.

- **Release decision:** the top-level pass/fail result.
- **Tasks:** task-level diffs, judge scores, reasons, and trace links.
- **Traces:** raw request/response evidence for a selected trace.
- **Gateway Activity:** raw operational evidence such as calls, cost, latency, alerts, and model breakdown.

Start it with:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/dashboard/`.

## Provider Support

OpenAI-compatible route:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: demo-session" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hi"}]}'
```

Anthropic Messages API route:

```bash
curl http://localhost:8000/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -H "X-Session-Id: anthropic-demo" \
  -d '{"model":"claude-3-5-sonnet-latest","max_tokens":128,"messages":[{"role":"user","content":"Say hi"}]}'
```

Streaming is supported for both routes. Streaming chunks are forwarded unchanged, and the gateway records best-effort usage and response summaries when the stream closes.

## Gateway Configuration

Environment variables are loaded from `.env`.

- `DATABASE_URL`: async SQLAlchemy URL for the FastAPI service.
- `DASHBOARD_DATABASE_URL`: sync PostgreSQL URL for dashboard queries.
- `OPENAI_BASE_URL`: upstream OpenAI-compatible API base URL.
- `ANTHROPIC_BASE_URL`: upstream Anthropic API base URL.
- `PRICING_CONFIG_PATH`: YAML pricing file path.
- `RECORD_REQUEST_BODY`, `RECORD_RESPONSE_BODY`, `MAX_BODY_BYTES`: request/response body storage guardrails.
- `GATEWAY_API_KEYS`: optional comma-separated gateway API keys. Empty disables gateway auth.
- `DEFAULT_TENANT_ID`: tenant label used when `X-Tenant-Id` is omitted.
- `ALERTS_ENABLED`, `ALERT_*`: optional anomaly detection and webhook alert configuration.

Gateway auth is separate from provider auth. If `GATEWAY_API_KEYS` is configured, send `X-Gateway-Api-Key` to the gateway. Provider credentials such as `Authorization` or `x-api-key` are still forwarded upstream.

Use `X-Tenant-Id` to label traces by caller. If omitted, traces use `DEFAULT_TENANT_ID`.

## Dashboard API

The React dashboard reads JSON from FastAPI endpoints under `/api/dashboard/*`:

- `/api/dashboard/filters`
- `/api/dashboard/summary`
- `/api/dashboard/spans`
- `/api/dashboard/traces/{trace_id}`
- `/api/dashboard/cost-trend`
- `/api/dashboard/model-breakdown`
- `/api/dashboard/alerts`
- `/api/dashboard/eval-reports`

These endpoints support the release review UI; they are not the primary user-facing interface.

## Test Strategy

Fast tests that do not call external networks or real OpenAI:

```powershell
.venv\Scripts\activate
python -m pytest -q
```

Frontend validation:

```powershell
cd frontend
npm install
npm run build
```

Coverage focus:

- Environment smoke: FastAPI app and `/health` can run.
- Unit tests: cost calculation, body/header sanitizing, streaming aggregation, recorder state transitions, dashboard tree building, gateway auth, Anthropic aggregation, and alert rules.
- Dashboard API: JSON serialization for Decimal/Timestamp values and record endpoints.
- Concurrency: concurrent `X-Session-Id` calls reuse one trace through the PostgreSQL partial unique index and upsert path.
- Streaming: mocked SSE forwarding verifies chunk passthrough, usage aggregation, and automatic OpenAI `stream_options.include_usage`.
- Crash tolerance: a span committed at request start remains visible as `in_progress` when it is never finished.

# Trajectory CI

Trajectory CI is a local regression testing platform for AI Agent systems. Run a baseline and a candidate version of your agent, compare their task trajectories, and get a clear release verdict:

```text
REGRESSION GATE: PASSED
```

or:

```text
REGRESSION GATE: FAILED
- regressed tasks 2 exceeded allowed 0
- cost increase 31.4 exceeded allowed 15
```

The gateway, traces, cost, latency, and dashboard are supporting infrastructure for that CI decision. They answer why a candidate failed the gate: which task regressed, which trace changed, whether a task did not run, and whether a cheaper/faster change made quality unacceptable.

## Why Not Just Use A Trace Tool?

General LLM observability tools are good at showing individual calls. Trajectory CI is built around release decisions for agent changes:

- **Regression-first:** the primary output is pass/fail for a baseline-vs-candidate run, not a pile of charts.
- **Trajectory diff:** each task stores both runs, judge reasons, hard-check failures, and trace IDs for drill-down.
- **Cost as a gate:** cost and latency are treated as release criteria, not just accounting metrics.
- **Zero-intrusion capture:** OpenAI-compatible and Anthropic clients only need a local `base_url` change.
- **Local-first:** traces and raw bodies can stay in your own Postgres while developing or demoing.

## Architecture

Agent client -> FastAPI proxy -> real LLM provider API. The proxy records traces/spans in PostgreSQL. `python -m eval compare` turns those traces into regression reports with gate verdicts. The React dashboard presents the latest gate status first, then lets you drill into calls, traces, cost, and eval task diffs.

## Case Study: Cheaper Prompt, Failed Gate

A real DeepSeek-backed evaluation in this repo compares two prompt profiles for the same agent tasks:

- `baseline`: concise but complete engineering answers with caveats and tradeoffs.
- `candidate`: aggressively shorter answers intended to reduce token usage and latency.

The candidate looked attractive on infrastructure metrics:

- Cost dropped from `$0.000579` to `$0.000188` (`-67.5%`).
- Average latency dropped from `10445ms` to `3646ms` (`-65.1%`).

But the regression gate still failed because the candidate omitted important debugging evidence in `failed_agent_investigation`:

```text
REGRESSION GATE: FAILED
- regressed tasks 1 exceeded allowed 0
```

Read the generated report at [`docs/reports/agent-release-quality.md`](docs/reports/agent-release-quality.md). This is the core reason Trajectory CI treats cost and trace data as release evidence, not as standalone dashboard trivia.

## Local setup

```powershell
.venv\Scripts\activate
uv pip install -e ".[dev]"
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Start the React dashboard in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The Vite dev server proxies `/api` requests to FastAPI on `http://127.0.0.1:8000`.

The previous Streamlit dashboard is kept as a legacy fallback:

```powershell
.venv\Scripts\activate
streamlit run dashboard\streamlit_app.py
```

## Use with an OpenAI-compatible client

Set the client's base URL to `http://localhost:8000/v1` and keep using your real provider API key. The gateway forwards the upstream auth header and does not store the key.

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: demo-session" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hi"}]}'
```

For streaming:

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: demo-session" \
  -d '{"model":"gpt-4o-mini","stream":true,"messages":[{"role":"user","content":"Say hi"}]}'
```

## Anthropic Messages API

The gateway proxies Anthropic Messages API calls at `POST /v1/messages`. The response shape stays Anthropic-native; the gateway only records trace, usage, latency, and cost metadata.

```bash
curl http://localhost:8000/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -H "X-Session-Id: anthropic-demo" \
  -d '{"model":"claude-3-5-sonnet-latest","max_tokens":128,"messages":[{"role":"user","content":"Say hi"}]}'
```

For streaming, send `"stream": true`; the gateway forwards Anthropic SSE chunks unchanged and records a best-effort aggregate response when the stream closes.

Run the interactive Anthropic tool-use example through the gateway:

```powershell
.venv\Scripts\activate
python example\anthropic_tool_agent_run.py "List the top-level files, then read README.md if it exists."
```

The script loads `.env`, sends requests to `http://127.0.0.1:8000/v1/messages`, and tags spans with `X-Session-Id` / `X-Tenant-Id` so they appear in the dashboard. Set `ANTHROPIC_API_KEY` in `.env`; set `MODEL_ID` if you want a model other than the script default.

## Gateway auth, tenants, and alerts

Gateway auth is optional and disabled by default. To enable it, set `GATEWAY_API_KEYS` to a comma-separated list and send `X-Gateway-Api-Key` on gateway requests. This is separate from upstream provider auth; `Authorization`, `x-api-key`, and provider version headers still pass through to the provider.

Use `X-Tenant-Id` to label traces by caller. If omitted, traces use `DEFAULT_TENANT_ID`.

Alerts are optional and disabled by default. When `ALERTS_ENABLED=true`, the gateway evaluates recent completed spans after each request and logs warnings for high error rate, high p95 latency, or model cost spikes. Set `ALERT_WEBHOOK_URL` to POST alert payloads to an external receiver.

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

These endpoints wrap the existing dashboard query layer and return JSON-safe records for the frontend.

## Test strategy

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

## Agent Regression CI

A task set defines the tasks your agent must keep passing and the release gate a candidate run must satisfy:

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
    checks:
      - type: response_contains
        keyword: "cost"
```

When running an agent for evaluation, tag each LLM call:

- `X-Eval-Task-Id`: task id from the YAML task set.
- `X-Eval-Run-Id`: run id, for example `baseline` or `candidate`.
- `X-Session-Id`: optional; keep it unique per task/run, for example `{task_set}:{task_id}:{run_id}`.

Run a baseline and candidate through your agent, then compare:

```powershell
.venv\Scripts\activate
python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline
```

The compare command prints a CI-style verdict and exits non-zero when the gate fails. Use `--no-fail-on-gate` if you want to inspect a failed report locally without failing the shell step.

```text
REGRESSION GATE: FAILED
- regressed tasks 1 exceeded allowed 0
Report: ...
```

Export a markdown report:

```powershell
python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline --export-markdown report.md
```

The React dashboard shows the latest Regression Gate first. Calls, Cost, and Trace views are investigation tools for explaining that red/green result.
## Configuration

Environment variables are loaded from `.env`.

- `DATABASE_URL`: async SQLAlchemy URL for the FastAPI service.
- `DASHBOARD_DATABASE_URL`: sync PostgreSQL URL for dashboard queries, for example `postgresql+psycopg://postgres:postgres@localhost:5432/agent_observability`.
- `OPENAI_BASE_URL`: upstream OpenAI-compatible API base URL.
- `ANTHROPIC_BASE_URL`: upstream Anthropic API base URL.
- `PRICING_CONFIG_PATH`: YAML pricing file path.
- `RECORD_REQUEST_BODY`, `RECORD_RESPONSE_BODY`, `MAX_BODY_BYTES`: request/response body storage guardrails.
- `GATEWAY_API_KEYS`: optional comma-separated gateway API keys. Empty disables gateway auth.
- `DEFAULT_TENANT_ID`: tenant label used when `X-Tenant-Id` is omitted.
- `ALERTS_ENABLED`, `ALERT_*`: optional anomaly detection and webhook alert configuration.

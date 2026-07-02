# Agent Observability Gateway

Zero-intrusion local gateway for OpenAI-compatible and Anthropic LLM agent calls: point an agent's `base_url` at this service and get traces, token usage, latency, and cost records without adding instrumentation to the agent code.

## Architecture

Agent client -> FastAPI proxy -> real LLM provider API. The proxy records traces/spans in PostgreSQL through SQLAlchemy async models. The React dashboard reads FastAPI dashboard APIs. Cost calculation uses a YAML pricing table.

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

## Phase 2 trajectory evaluation

Phase 2 compares two runs of the same task set using traces already captured by the gateway.

When running an agent for evaluation, add these headers to each LLM call:

- `X-Eval-Task-Id`: task id from the YAML task set.
- `X-Eval-Run-Id`: run id, for example `v1` or `v2`.
- `X-Session-Id`: optional. If used, keep it unique per task/run, for example `{task_set}:{task_id}:{run_id}`.

Task sets live under `eval/task_sets/`:

```yaml
tasks:
  - task_id: "hello_basic"
    description: "Basic hello response smoke test"
    input: "Hello"
    checks:
      - type: response_contains
        keyword: "Hello"
      - type: max_steps
        value: 8
```

Run a comparison:

```powershell
.venv\Scripts\activate
python -m eval compare --task-set bilibili_agent_v1 --run-id v2 --against v1 --skip-judge
```

Use `--skip-judge` for local hard-check-only validation. Omit it to call the configured judge model through the local gateway. Judge calls are tagged with `X-Span-Type: llm_judge`, and compare queries exclude judge spans from agent trajectory data.

Export a markdown report:

```powershell
python -m eval compare --task-set bilibili_agent_v1 --run-id v2 --against v1 --export-markdown report.md
```

The React dashboard has Eval and Trace views for historical reports, per-task diffs, and linked Phase 1 trace inspection.

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
# Agent Observability Gateway

Zero-intrusion local gateway for OpenAI-compatible LLM agent calls: point an agent's `base_url` at this service and get traces, token usage, latency, and cost records without adding instrumentation to the agent code.

## Architecture

Agent client -> FastAPI OpenAI-compatible proxy -> real OpenAI API. The proxy records traces/spans in PostgreSQL through SQLAlchemy async models. Streamlit reads PostgreSQL directly for the dashboard. Cost calculation uses a YAML pricing table.

## Local setup

```powershell
.venv\Scripts\activate
uv pip install -e ".[dev]"
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Start the dashboard in another terminal:

```powershell
.venv\Scripts\activate
streamlit run dashboard\streamlit_app.py
```

## Use with an OpenAI-compatible client

Set the client's base URL to `http://localhost:8000/v1` and keep using your real OpenAI API key. The gateway forwards the `Authorization` header and does not store the key.

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


## Test strategy

Fast tests that do not call external networks or real OpenAI:

```powershell
.venv\Scripts\activate
python -m pytest -q tests\test_unit_cost_calculator.py tests\test_unit_dashboard_tree.py tests\test_unit_sanitizer.py tests\test_unit_streaming.py tests\test_unit_trace_recorder.py tests\test_integration_environment.py tests\test_integration_openai_proxy.py tests\test_integration_openai_proxy_streaming.py
```

Full local validation, including PostgreSQL-backed concurrency and crash-tolerance checks:

```powershell
.venv\Scripts\activate
python -m pytest -q
```

Coverage focus:

- Environment smoke: FastAPI app and `/health` can run.
- Unit tests: cost calculation, body/header sanitizing, streaming aggregation, recorder state transitions, dashboard tree building.
- Concurrency: concurrent `X-Session-Id` calls reuse one trace through the PostgreSQL partial unique index and upsert path.
- Streaming: mocked SSE forwarding verifies chunk passthrough, usage aggregation, and automatic `stream_options.include_usage`.
- Crash tolerance: a span committed at request start remains visible as `in_progress` when it is never finished.
- Dashboard: recursive tree logic is covered by unit tests; visual layout should still be checked manually with Streamlit.


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

The Streamlit dashboard has an `Eval` tab for historical reports, per-task diffs, and linked Phase 1 trace trees.

## Configuration

Environment variables are loaded from `.env`.

- `DATABASE_URL`: async SQLAlchemy URL for the FastAPI service.
- `DASHBOARD_DATABASE_URL`: sync PostgreSQL URL for Streamlit, for example `postgresql+psycopg://postgres:postgres@localhost:5432/agent_observability`.
- `OPENAI_BASE_URL`: upstream OpenAI-compatible API base URL.
- `PRICING_CONFIG_PATH`: YAML pricing file path.
- `RECORD_REQUEST_BODY`, `RECORD_RESPONSE_BODY`, `MAX_BODY_BYTES`: request/response body storage guardrails.



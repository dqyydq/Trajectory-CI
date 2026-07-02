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
python -m pytest -q tests\unit tests\integration\test_environment.py tests\integration\test_openai_proxy.py tests\integration\test_openai_proxy_streaming.py
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

## Configuration

Environment variables are loaded from `.env`.

- `DATABASE_URL`: async SQLAlchemy URL for the FastAPI service.
- `DASHBOARD_DATABASE_URL`: sync PostgreSQL URL for Streamlit, for example `postgresql+psycopg://postgres:postgres@localhost:5432/agent_observability`.
- `OPENAI_BASE_URL`: upstream OpenAI-compatible API base URL.
- `PRICING_CONFIG_PATH`: YAML pricing file path.
- `RECORD_REQUEST_BODY`, `RECORD_RESPONSE_BODY`, `MAX_BODY_BYTES`: request/response body storage guardrails.



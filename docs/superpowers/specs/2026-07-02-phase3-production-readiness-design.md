# Phase 3 Production Readiness Design

## Goal

Phase 3 makes the gateway feel usable in production without turning it into a full observability platform. The scope is three focused capabilities:

- Anthropic Messages API support.
- Basic gateway authentication and tenant labeling.
- Lightweight anomaly detection with logging and optional webhook alerts.

The main architectural constraint is that tracing, cost calculation, body guardrails, and eval tagging remain shared. Adding Anthropic should not require duplicating the OpenAI proxy flow or changing `TraceRecorder`.

## Non-Goals

- Full RBAC, user management, or per-tenant dashboards.
- Persistent alert lifecycle management, deduplication windows, silencing, or notification routing.
- Complete Anthropic API surface beyond Messages-compatible LLM calls.
- Cross-provider response normalization for clients. The gateway should return each provider's native response shape.

## Architecture

### Protocol Adapters

Introduce a small adapter boundary under `app/protocols/`.

Each adapter owns:

- Route registration shape.
- Upstream URL construction.
- Request model extraction for tracing and pricing.
- Streaming aggregation rules.
- Error extraction.

Shared logic remains:

- `TraceRecorder.start_span` and `finish_span`.
- Request/response body truncation.
- eval headers: `X-Eval-Task-Id`, `X-Eval-Run-Id`, `X-Span-Type`.
- session correlation through `X-Session-Id`.
- cost calculation through `CostCalculator`.
- alert evaluation after a span is finished.

OpenAI continues to expose:

- `POST /v1/chat/completions`

Anthropic adds:

- `POST /v1/messages`

The Anthropic upstream base URL is configured independently from OpenAI-compatible APIs.

### Authentication and Tenancy

Gateway authentication uses a separate header:

- `X-Gateway-Api-Key`

This avoids colliding with `Authorization`, which must continue to pass through to upstream providers.

Configuration:

- `GATEWAY_API_KEYS`: comma-separated allowed keys. Empty means gateway auth is disabled.
- `DEFAULT_TENANT_ID`: fallback tenant when no tenant header is provided.

Tenant labeling uses:

- `X-Tenant-Id`

`tenant_id` is stored on `traces`. Phase 3 only labels data by tenant; it does not implement hard dashboard isolation. API requests may optionally validate tenant/key pairs later, but Phase 3 keeps keys global to avoid designing a premature permission model.

Auth behavior:

- If `GATEWAY_API_KEYS` is empty, all requests are accepted.
- If configured, missing or invalid `X-Gateway-Api-Key` returns `401`.
- The upstream `Authorization` header is never used for gateway auth and is still forwarded after hop-by-hop filtering.

### Alert Rules

Add an alert service under `app/alerts/`.

The service runs after a span is finished and evaluates rules against recent database data:

- Error rate: in the last N minutes, error spans divided by completed spans exceeds threshold.
- Latency: p95 latency in the last N minutes exceeds threshold.
- Model cost spike: current N-minute model cost exceeds previous N-minute cost by a multiplier and a minimum absolute cost.

Configuration:

- `ALERTS_ENABLED`: default `false`.
- `ALERT_WINDOW_MINUTES`: default `5`.
- `ALERT_ERROR_RATE_THRESHOLD`: default `0.2`.
- `ALERT_MIN_REQUESTS`: default `10`.
- `ALERT_P95_LATENCY_MS`: default `30000`.
- `ALERT_COST_SPIKE_MULTIPLIER`: default `3.0`.
- `ALERT_MIN_COST_USD`: default `1.0`.
- `ALERT_WEBHOOK_URL`: optional.

Alert delivery:

- Always write a structured warning log when a rule fires.
- If `ALERT_WEBHOOK_URL` is set, POST a JSON payload with rule name, severity, window, tenant id, model when applicable, and metrics.
- Webhook failures are logged but do not fail the proxied LLM request.

Phase 3 does not persist alerts in the database. That keeps the feature small and avoids adding lifecycle semantics before the dashboard needs them.

## Data Model

Add to `traces`:

- `tenant_id VARCHAR(255) NOT NULL DEFAULT 'default'`

Add indexes:

- `(tenant_id, started_at)` for dashboard and alert filtering.
Do not add a tenant-scoped eval composite index in Phase 3. Existing eval queries are not tenant-scoped yet, so adding that index now would increase write cost without serving a current query path.

`spans` does not need `tenant_id` because it can join through `traces`. This avoids duplicated tenant state.

## Data Flow

1. Request enters a provider route.
2. Gateway auth dependency validates `X-Gateway-Api-Key` if configured.
3. Tenant context is read from `X-Tenant-Id` or `DEFAULT_TENANT_ID`.
4. Adapter extracts model, stream flag, trace request body, and upstream request body.
5. `TraceRecorder.start_span` creates an `in_progress` span and labels the trace with tenant/eval/session metadata.
6. Adapter calls upstream and streams or returns the provider-native response.
7. Adapter aggregates usage and response details where possible.
8. `TraceRecorder.finish_span` marks the span success/error and updates trace `ended_at`.
9. Alert service evaluates recent data and logs/sends webhook alerts.

## Anthropic Details

Non-streaming:

- Forward request to `{ANTHROPIC_BASE_URL}/messages`.
- Preserve Anthropic-native response.
- Extract model from request body `model`.
- Extract usage from response body `usage.input_tokens` and `usage.output_tokens`.

Streaming:

- Forward SSE response unchanged.
- Aggregate `message_start`, `content_block_delta`, `message_delta`, and `message_stop` events best-effort.
- Usage should be read from Anthropic stream events when present.
- If usage cannot be determined, finish the span without token/cost fields rather than failing the user request.

Headers:

- Hop-by-hop headers are stripped.
- Gateway-only headers are stripped before forwarding: `X-Gateway-Api-Key`, `X-Tenant-Id`, `X-Session-Id`, `X-Eval-Task-Id`, `X-Eval-Run-Id`, `X-Span-Type`.
- Provider auth/version headers are forwarded as supplied by the caller.

## Error Handling

- Auth failures return `401` before creating a span.
- Upstream non-2xx responses create an error span and return the upstream status/body.
- Streaming exceptions finish the span with `error` and re-raise so the HTTP connection reflects the failure.
- Alert evaluation exceptions are logged and swallowed.
- Webhook delivery is best effort and never blocks the proxied response longer than a short timeout.

## Testing

Unit tests:

- Gateway auth enabled/disabled behavior.
- Tenant extraction defaults.
- Anthropic usage extraction for non-streaming.
- Anthropic stream aggregation best-effort behavior.
- Alert rule calculations for error rate, latency, and cost spike.
- Gateway-only header stripping.

Integration tests:

- OpenAI route still works with auth disabled.
- OpenAI route rejects missing key when auth enabled.
- Anthropic non-streaming route records a successful span.
- Anthropic streaming route records a successful span.
- Alert service logs or posts webhook payload without breaking the request.
- Tenant id is persisted on traces.

Regression tests:

- Existing Phase 1 and Phase 2 tests must continue passing.
- Concurrent trace creation must still deduplicate by `session_id`.
- Eval compare must still find traces by `eval_task_id` and `eval_run_id`.

## Implementation Order

1. Add config and auth dependency.
2. Add `tenant_id` migration/model/recorder support.
3. Refactor header filtering to strip gateway-only headers.
4. Add Anthropic client/route using the existing recorder lifecycle.
5. Add alert rule service and call it after span finish.
6. Add tests for auth, tenant persistence, Anthropic, and alerts.
7. Update README and `.env.example`.


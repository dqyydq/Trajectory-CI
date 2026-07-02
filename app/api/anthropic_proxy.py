from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.service import evaluate_alerts
from app.core.config import Settings, get_settings
from app.db.models import SpanStatus, SpanType
from app.db.session import get_db_session
from app.protocols.anthropic import aggregate_anthropic_stream, anthropic_usage, parse_anthropic_sse_line
from app.protocols.common import calculate_cost, enforce_gateway_auth, response_headers, tenant_id_from_request
from app.proxy.anthropic_client import AnthropicProxyClient
from app.tracing.recorder import TraceRecorder
from app.tracing.schemas import SpanResult

router = APIRouter()


def _error_message(body: Any) -> str | None:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)
        if error is not None:
            return str(error)
    return None


def _span_type_from_request(request: Request) -> SpanType:
    try:
        return SpanType(request.headers.get("X-Span-Type", SpanType.llm_call.value))
    except ValueError:
        return SpanType.llm_call


@router.post("/v1/messages")
async def messages(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    enforce_gateway_auth(request, settings)
    body = await request.json()
    is_stream = bool(body.get("stream"))
    tenant_id = tenant_id_from_request(request, settings)
    recorder = TraceRecorder(db_session, settings)
    handle = await recorder.start_span(
        session_id=request.headers.get("X-Session-Id"),
        model=body.get("model"),
        request_body=body,
        is_stream=is_stream,
        span_type=_span_type_from_request(request),
        eval_task_id=request.headers.get("X-Eval-Task-Id"),
        eval_run_id=request.headers.get("X-Eval-Run-Id"),
        tenant_id=tenant_id,
    )

    if is_stream:
        return await _streaming_response(request, body, recorder, handle, settings, db_session, tenant_id)
    return await _non_streaming_response(request, body, recorder, handle, settings, db_session, tenant_id)


async def _non_streaming_response(
    request: Request,
    body: dict[str, Any],
    recorder: TraceRecorder,
    handle: Any,
    settings: Settings,
    db_session: AsyncSession,
    tenant_id: str,
) -> Response:
    client = AnthropicProxyClient(settings)
    upstream = await client.post_messages(headers=dict(request.headers), body=body)
    try:
        response_body = upstream.json()
    except ValueError:
        response_body = {"raw": upstream.text}

    prompt_tokens, completion_tokens, total_tokens = anthropic_usage(response_body if isinstance(response_body, dict) else None)
    cost = calculate_cost(
        settings=settings,
        model=body.get("model"),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    await recorder.finish_span(
        handle,
        SpanResult(
            status=SpanStatus.success if upstream.is_success else SpanStatus.error,
            response_body=response_body,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            error_message=None if upstream.is_success else _error_message(response_body),
        ),
    )
    await evaluate_alerts(session=db_session, settings=settings, tenant_id=tenant_id, model=body.get("model"))
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        headers=response_headers(dict(upstream.headers)),
    )


async def _streaming_response(
    request: Request,
    body: dict[str, Any],
    recorder: TraceRecorder,
    handle: Any,
    settings: Settings,
    db_session: AsyncSession,
    tenant_id: str,
) -> Response:
    client = AnthropicProxyClient(settings)
    http_client, upstream, context = await client.stream_messages(headers=dict(request.headers), body=body)

    if not upstream.is_success:
        content = await upstream.aread()
        try:
            response_body: Any = upstream.json()
        except ValueError:
            response_body = {"raw": content.decode("utf-8", errors="ignore")}
        await context.__aexit__(None, None, None)
        await http_client.aclose()
        await recorder.finish_span(
            handle,
            SpanResult(status=SpanStatus.error, response_body=response_body, error_message=_error_message(response_body)),
        )
        await evaluate_alerts(session=db_session, settings=settings, tenant_id=tenant_id, model=body.get("model"))
        return Response(
            content=content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type"),
            headers=response_headers(dict(upstream.headers)),
        )

    events: list[dict[str, Any]] = []

    async def generate() -> AsyncIterator[bytes]:
        try:
            async for line in upstream.aiter_lines():
                raw = f"{line}\n".encode("utf-8")
                parsed = parse_anthropic_sse_line(raw)
                if parsed is not None:
                    events.append(parsed)
                yield raw
            response_body = aggregate_anthropic_stream(events)
            prompt_tokens, completion_tokens, total_tokens = anthropic_usage(response_body)
            cost = calculate_cost(
                settings=settings,
                model=body.get("model"),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            await recorder.finish_span(
                handle,
                SpanResult(
                    status=SpanStatus.success,
                    response_body=response_body,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost,
                ),
            )
            await evaluate_alerts(session=db_session, settings=settings, tenant_id=tenant_id, model=body.get("model"))
        except Exception as exc:
            await recorder.finish_span(
                handle,
                SpanResult(status=SpanStatus.error, response_body={"_stream_events": events}, error_message=str(exc)),
            )
            await evaluate_alerts(session=db_session, settings=settings, tenant_id=tenant_id, model=body.get("model"))
            raise
        finally:
            await context.__aexit__(None, None, None)
            await http_client.aclose()

    return StreamingResponse(
        generate(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type") or "text/event-stream",
        headers=response_headers(dict(upstream.headers)),
    )

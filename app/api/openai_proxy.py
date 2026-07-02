from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.cost.calculator import CostCalculator
from app.cost.pricing import PricingTable
from app.db.models import SpanStatus
from app.db.session import get_db_session
from app.proxy.openai_client import OpenAIProxyClient
from app.proxy.streaming import aggregate_openai_stream, ensure_stream_usage, parse_sse_data_line
from app.tracing.recorder import TraceRecorder
from app.tracing.schemas import SpanResult

router = APIRouter()


def _usage(response_body: dict[str, Any] | None) -> tuple[int | None, int | None, int | None]:
    usage = (response_body or {}).get("usage") or {}
    return usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens")


def _error_message(body: Any) -> str | None:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)
    return None


def _response_headers(headers: dict[str, str]) -> dict[str, str]:
    excluded = {"content-length", "content-encoding", "transfer-encoding", "connection"}
    return {key: value for key, value in headers.items() if key.lower() not in excluded}


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    body = await request.json()
    is_stream = bool(body.get("stream"))
    session_id = request.headers.get("X-Session-Id")
    recorder = TraceRecorder(db_session, settings)
    handle = await recorder.start_span(
        session_id=session_id,
        model=body.get("model"),
        request_body=body,
        is_stream=is_stream,
    )

    if is_stream:
        return await _streaming_response(request, body, recorder, handle, settings)
    return await _non_streaming_response(request, body, recorder, handle, settings)


async def _non_streaming_response(
    request: Request,
    body: dict[str, Any],
    recorder: TraceRecorder,
    handle: Any,
    settings: Settings,
) -> Response:
    client = OpenAIProxyClient(settings)
    upstream = await client.post_chat_completions(headers=dict(request.headers), body=body)
    try:
        response_body = upstream.json()
    except ValueError:
        response_body = {"raw": upstream.text}

    prompt_tokens, completion_tokens, total_tokens = _usage(response_body if isinstance(response_body, dict) else None)
    cost = CostCalculator(PricingTable.from_yaml(settings.pricing_config_path)).calculate(
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
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        headers=_response_headers(dict(upstream.headers)),
    )


async def _streaming_response(
    request: Request,
    body: dict[str, Any],
    recorder: TraceRecorder,
    handle: Any,
    settings: Settings,
) -> Response:
    forwarded_body = ensure_stream_usage(body)
    client = OpenAIProxyClient(settings)
    http_client, upstream, context = await client.stream_chat_completions(
        headers=dict(request.headers),
        body=forwarded_body,
    )

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
            SpanResult(
                status=SpanStatus.error,
                response_body=response_body,
                error_message=_error_message(response_body),
            ),
        )
        return Response(
            content=content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type"),
            headers=_response_headers(dict(upstream.headers)),
        )

    chunks: list[dict[str, Any]] = []

    async def generate() -> AsyncIterator[bytes]:
        try:
            async for line in upstream.aiter_lines():
                raw = f"{line}\n".encode("utf-8")
                parsed = parse_sse_data_line(raw)
                if parsed is not None:
                    chunks.append(parsed)
                yield raw
            response_body = aggregate_openai_stream(chunks)
            prompt_tokens, completion_tokens, total_tokens = _usage(response_body)
            cost = CostCalculator(PricingTable.from_yaml(settings.pricing_config_path)).calculate(
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
        except Exception as exc:
            await recorder.finish_span(
                handle,
                SpanResult(status=SpanStatus.error, response_body={"_stream_chunks": chunks}, error_message=str(exc)),
            )
            raise
        finally:
            await context.__aexit__(None, None, None)
            await http_client.aclose()

    return StreamingResponse(
        generate(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type") or "text/event-stream",
        headers=_response_headers(dict(upstream.headers)),
    )




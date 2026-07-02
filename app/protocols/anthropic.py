from __future__ import annotations

import json
from typing import Any


def anthropic_usage(response_body: dict[str, Any] | None) -> tuple[int | None, int | None, int | None]:
    usage = (response_body or {}).get("usage") or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total = None
    if input_tokens is not None and output_tokens is not None:
        total = input_tokens + output_tokens
    return input_tokens, output_tokens, total


def parse_anthropic_sse_line(line: bytes) -> dict[str, Any] | None:
    text = line.decode("utf-8", errors="ignore").strip()
    if not text.startswith("data:"):
        return None
    payload = text[5:].strip()
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def aggregate_anthropic_stream(events: list[dict[str, Any]]) -> dict[str, Any]:
    content_parts: list[str] = []
    response_id: str | None = None
    model: str | None = None
    usage: dict[str, int] = {}

    for event in events:
        event_type = event.get("type")
        if event_type == "message_start":
            message = event.get("message") or {}
            response_id = message.get("id") or response_id
            model = message.get("model") or model
            usage.update(message.get("usage") or {})
        elif event_type == "content_block_delta":
            delta = event.get("delta") or {}
            text = delta.get("text")
            if text:
                content_parts.append(text)
        elif event_type == "message_delta":
            usage.update(event.get("usage") or {})

    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = None
    if input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    response: dict[str, Any] = {
        "id": response_id,
        "model": model,
        "type": "message",
        "content": [{"type": "text", "text": "".join(content_parts)}],
        "usage": usage or None,
        "_stream_events": events,
    }
    if total_tokens is not None:
        response["_total_tokens"] = total_tokens
    return response

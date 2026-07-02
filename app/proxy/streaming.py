from __future__ import annotations

import json
from typing import Any


def ensure_stream_usage(request_body: dict[str, Any]) -> dict[str, Any]:
    forwarded = dict(request_body)
    options = dict(forwarded.get("stream_options") or {})
    options["include_usage"] = True
    forwarded["stream_options"] = options
    return forwarded


def parse_sse_data_line(line: bytes) -> dict[str, Any] | None:
    text = line.decode("utf-8", errors="ignore").strip()
    if not text.startswith("data:"):
        return None
    payload = text[5:].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def aggregate_openai_stream(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    content_parts: list[str] = []
    usage: dict[str, int] | None = None
    model: str | None = None
    response_id: str | None = None

    for chunk in chunks:
        model = chunk.get("model") or model
        response_id = chunk.get("id") or response_id
        if chunk.get("usage"):
            usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            content = delta.get("content")
            if content:
                content_parts.append(content)

    return {
        "id": response_id,
        "model": model,
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": "".join(content_parts)}}],
        "usage": usage,
        "_stream_chunks": chunks,
    }


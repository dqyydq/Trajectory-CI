from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def upstream_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


class OpenAIProxyClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def chat_completions_url(self) -> str:
        return f"{self.settings.openai_base_url.rstrip('/')}/chat/completions"

    async def post_chat_completions(
        self,
        *,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            return await client.post(self.chat_completions_url, headers=upstream_headers(headers), json=body)

    async def stream_chat_completions(
        self,
        *,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> tuple[httpx.AsyncClient, httpx.Response, Any]:
        client = httpx.AsyncClient(timeout=None)
        context = client.stream("POST", self.chat_completions_url, headers=upstream_headers(headers), json=body)
        response = await context.__aenter__()
        return client, response, context


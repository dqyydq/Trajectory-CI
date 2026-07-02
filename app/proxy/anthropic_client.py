from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.protocols.common import upstream_headers


class AnthropicProxyClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def messages_url(self) -> str:
        return f"{self.settings.anthropic_base_url.rstrip('/')}/messages"

    async def post_messages(
        self,
        *,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            return await client.post(self.messages_url, headers=upstream_headers(headers), json=body)

    async def stream_messages(
        self,
        *,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> tuple[httpx.AsyncClient, httpx.Response, Any]:
        client = httpx.AsyncClient(timeout=None)
        context = client.stream("POST", self.messages_url, headers=upstream_headers(headers), json=body)
        response = await context.__aenter__()
        return client, response, context

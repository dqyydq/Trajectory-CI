from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.alerts import service
from app.core.config import Settings
from app.db.models import SpanStatus


@dataclass(frozen=True)
class FakeRow:
    status: SpanStatus | None = None
    latency_ms: int | None = None
    cost_usd: Decimal | None = None
    model: str | None = None


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, statement):
        return FakeResult(self.results.pop(0))


@pytest.mark.asyncio
async def test_alert_rules_detect_error_latency_and_cost_spike(monkeypatch) -> None:
    delivered = []

    async def fake_deliver(event, settings):
        delivered.append(event)

    monkeypatch.setattr(service, "_deliver_alert", fake_deliver)
    session = FakeSession(
        [
            [
                FakeRow(SpanStatus.error, 60000, Decimal("2.00"), "model-a"),
                FakeRow(SpanStatus.success, 61000, Decimal("2.00"), "model-a"),
                FakeRow(SpanStatus.success, 62000, Decimal("2.00"), "model-a"),
            ],
            [FakeRow(cost_usd=Decimal("1.00"))],
        ]
    )
    settings = Settings(
        alerts_enabled=True,
        alert_min_requests=3,
        alert_error_rate_threshold=0.2,
        alert_p95_latency_ms=1000,
        alert_cost_spike_multiplier=3.0,
        alert_min_cost_usd=1.0,
    )

    events = await service.evaluate_alerts(session=session, settings=settings, tenant_id="tenant-a", model="model-a")

    assert [event.rule for event in events] == ["error_rate", "p95_latency", "model_cost_spike"]
    assert delivered == events


@pytest.mark.asyncio
async def test_alert_webhook_failure_does_not_raise(monkeypatch) -> None:
    class FailingClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json):
            raise RuntimeError("webhook down")

    monkeypatch.setattr(service.httpx, "AsyncClient", FailingClient)
    event = service.AlertEvent("error_rate", "warning", "tenant-a", 5, {"error_rate": 1.0})

    await service._deliver_alert(event, Settings(alert_webhook_url="http://webhook.local"))
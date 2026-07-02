from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Span, SpanStatus, Trace

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlertEvent:
    rule: str
    severity: str
    tenant_id: str
    window_minutes: int
    metrics: dict[str, Any]
    model: str | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "tenant_id": self.tenant_id,
            "window_minutes": self.window_minutes,
            "model": self.model,
            "metrics": self.metrics,
        }


async def evaluate_alerts(
    *,
    session: AsyncSession,
    settings: Settings,
    tenant_id: str,
    model: str | None,
) -> list[AlertEvent]:
    if not settings.alerts_enabled:
        return []

    try:
        events = await _evaluate_alerts(session=session, settings=settings, tenant_id=tenant_id, model=model)
        for event in events:
            await _deliver_alert(event, settings)
        return events
    except Exception:
        logger.exception("Alert evaluation failed")
        return []


async def _evaluate_alerts(
    *,
    session: AsyncSession,
    settings: Settings,
    tenant_id: str,
    model: str | None,
) -> list[AlertEvent]:
    now = datetime.now(UTC)
    window = timedelta(minutes=settings.alert_window_minutes)
    current_start = now - window
    previous_start = now - (window * 2)

    completed_spans = (
        await session.execute(
            select(Span.status, Span.latency_ms, Span.cost_usd, Span.model)
            .join(Trace, Trace.trace_id == Span.trace_id)
            .where(
                Trace.tenant_id == tenant_id,
                Span.ended_at.is_not(None),
                Span.ended_at >= current_start,
                Span.ended_at <= now,
            )
        )
    ).all()

    events: list[AlertEvent] = []
    request_count = len(completed_spans)
    if request_count >= settings.alert_min_requests:
        error_count = sum(1 for row in completed_spans if row.status == SpanStatus.error)
        error_rate = error_count / request_count if request_count else 0.0
        if error_rate > settings.alert_error_rate_threshold:
            events.append(
                AlertEvent(
                    rule="error_rate",
                    severity="warning",
                    tenant_id=tenant_id,
                    window_minutes=settings.alert_window_minutes,
                    metrics={"request_count": request_count, "error_count": error_count, "error_rate": error_rate},
                )
            )

        latencies = sorted(row.latency_ms for row in completed_spans if row.latency_ms is not None)
        if latencies:
            index = max(0, min(len(latencies) - 1, int(len(latencies) * 0.95) - 1))
            p95 = latencies[index]
            if p95 > settings.alert_p95_latency_ms:
                events.append(
                    AlertEvent(
                        rule="p95_latency",
                        severity="warning",
                        tenant_id=tenant_id,
                        window_minutes=settings.alert_window_minutes,
                        metrics={"request_count": request_count, "p95_latency_ms": p95},
                    )
                )

    if model:
        current_cost = _sum_cost(row.cost_usd for row in completed_spans if row.model == model)
        previous_rows = (
            await session.execute(
                select(Span.cost_usd)
                .join(Trace, Trace.trace_id == Span.trace_id)
                .where(
                    Trace.tenant_id == tenant_id,
                    Span.model == model,
                    Span.ended_at.is_not(None),
                    Span.ended_at >= previous_start,
                    Span.ended_at < current_start,
                )
            )
        ).all()
        previous_cost = _sum_cost(row.cost_usd for row in previous_rows)
        if current_cost >= Decimal(str(settings.alert_min_cost_usd)) and previous_cost > 0:
            multiplier = current_cost / previous_cost
            if multiplier > Decimal(str(settings.alert_cost_spike_multiplier)):
                events.append(
                    AlertEvent(
                        rule="model_cost_spike",
                        severity="warning",
                        tenant_id=tenant_id,
                        window_minutes=settings.alert_window_minutes,
                        model=model,
                        metrics={
                            "current_cost_usd": str(current_cost),
                            "previous_cost_usd": str(previous_cost),
                            "multiplier": float(multiplier),
                        },
                    )
                )

    return events


def _sum_cost(values: Any) -> Decimal:
    total = Decimal("0")
    for value in values:
        if value is not None:
            total += Decimal(value)
    return total


async def _deliver_alert(event: AlertEvent, settings: Settings) -> None:
    payload = event.payload()
    logger.warning("Observability alert fired", extra={"alert": payload})
    if not settings.alert_webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(settings.alert_webhook_url, json=payload)
    except Exception:
        logger.exception("Alert webhook delivery failed")

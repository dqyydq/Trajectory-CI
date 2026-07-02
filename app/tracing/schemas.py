from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.db.models import SpanStatus


@dataclass(frozen=True)
class SpanHandle:
    trace_id: uuid.UUID
    span_id: uuid.UUID
    started_at: datetime


@dataclass(frozen=True)
class SpanResult:
    status: SpanStatus
    response_body: dict | list | None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: Decimal | None = None
    error_message: str | None = None


from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from dashboard.queries import (
    load_alert_snapshot,
    load_cost_trend,
    load_eval_reports,
    load_eval_task_results,
    load_filter_options,
    load_health_summary,
    load_model_breakdown,
    load_spans,
    load_trace_spans,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if value is pd.NA:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [_jsonable(row) for row in frame.to_dict("records")]


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@router.get("/filters")
def filters(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return _jsonable(load_filter_options(settings.dashboard_database_url))


@router.get("/summary")
def summary(
    tenant_id: str | None = None,
    model: str | None = None,
    hours: int = Query(default=24, ge=1, le=720),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return _jsonable(
        load_health_summary(
            settings.dashboard_database_url,
            tenant_id=_optional(tenant_id),
            model=_optional(model),
            hours=hours,
        )
    )


@router.get("/spans")
def spans(
    trace_id: str | None = None,
    session_id: str | None = None,
    tenant_id: str | None = None,
    model: str | None = None,
    status: str | None = None,
    hours: int = Query(default=24, ge=1, le=720),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    return _records(
        load_spans(
            settings.dashboard_database_url,
            trace_id=_optional(trace_id),
            session_id=_optional(session_id),
            tenant_id=_optional(tenant_id),
            model=_optional(model),
            status=_optional(status),
            hours=hours,
        )
    )


@router.get("/traces/{trace_id}")
def trace_spans(trace_id: str, settings: Settings = Depends(get_settings)) -> list[dict[str, Any]]:
    return _records(load_trace_spans(settings.dashboard_database_url, trace_id))


@router.get("/cost-trend")
def cost_trend(
    tenant_id: str | None = None,
    model: str | None = None,
    hours: int = Query(default=24, ge=1, le=720),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    return _records(
        load_cost_trend(
            settings.dashboard_database_url,
            tenant_id=_optional(tenant_id),
            model=_optional(model),
            hours=hours,
        )
    )


@router.get("/model-breakdown")
def model_breakdown(
    tenant_id: str | None = None,
    hours: int = Query(default=24, ge=1, le=720),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    return _records(load_model_breakdown(settings.dashboard_database_url, tenant_id=_optional(tenant_id), hours=hours))


@router.get("/alerts")
def alerts(
    tenant_id: str | None = None,
    model: str | None = None,
    hours: int = Query(default=24, ge=1, le=720),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    return _records(
        load_alert_snapshot(
            settings.dashboard_database_url,
            tenant_id=_optional(tenant_id),
            model=_optional(model),
            hours=hours,
        )
    )


@router.get("/eval-reports")
def eval_reports(settings: Settings = Depends(get_settings)) -> list[dict[str, Any]]:
    return _records(load_eval_reports(settings.dashboard_database_url))


@router.get("/eval-reports/{report_id}/tasks")
def eval_report_tasks(report_id: str, settings: Settings = Depends(get_settings)) -> list[dict[str, Any]]:
    return _records(load_eval_task_results(settings.dashboard_database_url, report_id))
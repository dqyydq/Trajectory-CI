from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text


def _engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def _time_clause(column: str, hours: int | None, params: dict[str, Any]) -> str:
    if not hours:
        return ""
    params["hours"] = hours
    return f"{column} >= now() - (:hours * interval '1 hour')"


def load_filter_options(database_url: str):
    query = text(
        """
        SELECT
            array_remove(array_agg(DISTINCT t.tenant_id ORDER BY t.tenant_id), NULL) AS tenants,
            array_remove(array_agg(DISTINCT s.model ORDER BY s.model), NULL) AS models
        FROM traces t
        LEFT JOIN spans s ON s.trace_id = t.trace_id
        """
    )
    df = pd.read_sql(query, _engine(database_url))
    if df.empty:
        return {"tenants": [], "models": []}
    return {"tenants": df.iloc[0]["tenants"] or [], "models": df.iloc[0]["models"] or []}


def load_health_summary(
    database_url: str,
    *,
    tenant_id: str | None,
    model: str | None,
    hours: int,
):
    where = []
    params: dict[str, Any] = {"hours": hours}
    if tenant_id:
        where.append("t.tenant_id = :tenant_id")
        params["tenant_id"] = tenant_id
    if model:
        where.append("s.model = :model")
        params["model"] = model
    where.append("s.started_at >= now() - (:hours * interval '1 hour')")
    clause = "WHERE " + " AND ".join(where)
    query = text(
        f"""
        SELECT
            count(*) AS call_count,
            coalesce(sum(CASE WHEN s.status = 'error' THEN 1 ELSE 0 END), 0) AS error_count,
            coalesce(sum(CASE WHEN s.status = 'in_progress' THEN 1 ELSE 0 END), 0) AS in_progress_count,
            coalesce(sum(s.cost_usd), 0) AS cost_usd,
            coalesce(avg(s.latency_ms), 0) AS avg_latency_ms,
            coalesce(percentile_disc(0.95) WITHIN GROUP (ORDER BY s.latency_ms), 0) AS p95_latency_ms,
            coalesce(sum(s.total_tokens), 0) AS total_tokens,
            count(DISTINCT s.trace_id) AS trace_count
        FROM spans s
        JOIN traces t ON t.trace_id = s.trace_id
        {clause}
        """
    )
    return pd.read_sql(query, _engine(database_url), params=params).iloc[0].to_dict()


def load_spans(
    database_url: str,
    *,
    trace_id: str | None,
    session_id: str | None,
    model: str | None,
    status: str | None,
    tenant_id: str | None = None,
    hours: int | None = None,
):
    where = []
    params: dict[str, Any] = {}
    if trace_id:
        where.append("s.trace_id::text = :trace_id")
        params["trace_id"] = trace_id
    if session_id:
        where.append("t.session_id = :session_id")
        params["session_id"] = session_id
    if tenant_id:
        where.append("t.tenant_id = :tenant_id")
        params["tenant_id"] = tenant_id
    if model:
        where.append("s.model = :model")
        params["model"] = model
    if status:
        where.append("s.status = :status")
        params["status"] = status
    time_filter = _time_clause("s.started_at", hours, params)
    if time_filter:
        where.append(time_filter)
    clause = "WHERE " + " AND ".join(where) if where else ""
    query = text(
        f"""
        SELECT s.span_id::text, s.trace_id::text, t.session_id, t.tenant_id, s.parent_span_id::text,
               s.span_type, s.model, s.status, s.is_stream, s.prompt_tokens, s.completion_tokens,
               s.total_tokens, s.cost_usd, s.latency_ms, s.started_at, s.ended_at
        FROM spans s
        JOIN traces t ON t.trace_id = s.trace_id
        {clause}
        ORDER BY s.started_at DESC
        LIMIT 250
        """
    )
    return pd.read_sql(query, _engine(database_url), params=params)


def load_trace_spans(database_url: str, trace_id: str):
    query = text(
        """
        SELECT span_id::text, parent_span_id::text, span_type, model, status, is_stream, latency_ms,
               prompt_tokens, completion_tokens, total_tokens, cost_usd, started_at, ended_at,
               request_body, response_body, error_message
        FROM spans
        WHERE trace_id::text = :trace_id
        ORDER BY started_at ASC
        """
    )
    return pd.read_sql(query, _engine(database_url), params={"trace_id": trace_id})


def load_cost_trend(
    database_url: str,
    *,
    tenant_id: str | None = None,
    model: str | None = None,
    hours: int | None = None,
):
    where = ["s.status IN ('success', 'error')"]
    params: dict[str, Any] = {}
    if tenant_id:
        where.append("t.tenant_id = :tenant_id")
        params["tenant_id"] = tenant_id
    if model:
        where.append("s.model = :model")
        params["model"] = model
    time_filter = _time_clause("s.started_at", hours, params)
    if time_filter:
        where.append(time_filter)
    query = text(
        f"""
        SELECT date_trunc('hour', s.started_at) AS hour,
               count(*) AS call_count,
               coalesce(sum(s.cost_usd), 0) AS cost_usd,
               coalesce(avg(s.latency_ms), 0) AS avg_latency_ms
        FROM spans s
        JOIN traces t ON t.trace_id = s.trace_id
        WHERE {' AND '.join(where)}
        GROUP BY 1
        ORDER BY 1
        """
    )
    return pd.read_sql(query, _engine(database_url), params=params)


def load_model_breakdown(database_url: str, *, tenant_id: str | None, hours: int):
    where = ["s.started_at >= now() - (:hours * interval '1 hour')"]
    params: dict[str, Any] = {"hours": hours}
    if tenant_id:
        where.append("t.tenant_id = :tenant_id")
        params["tenant_id"] = tenant_id
    query = text(
        f"""
        SELECT coalesce(s.model, 'unknown') AS model,
               count(*) AS calls,
               coalesce(sum(CASE WHEN s.status = 'error' THEN 1 ELSE 0 END), 0) AS errors,
               coalesce(sum(s.cost_usd), 0) AS cost_usd,
               coalesce(avg(s.latency_ms), 0) AS avg_latency_ms
        FROM spans s
        JOIN traces t ON t.trace_id = s.trace_id
        WHERE {' AND '.join(where)}
        GROUP BY 1
        ORDER BY cost_usd DESC, calls DESC
        LIMIT 20
        """
    )
    return pd.read_sql(query, _engine(database_url), params=params)


def load_alert_snapshot(database_url: str, *, tenant_id: str | None, model: str | None, hours: int):
    summary = load_health_summary(database_url, tenant_id=tenant_id, model=model, hours=hours)
    calls = int(summary.get("call_count") or 0)
    errors = int(summary.get("error_count") or 0)
    error_rate = errors / calls if calls else 0.0
    p95_latency = float(summary.get("p95_latency_ms") or 0)
    alerts = []
    if calls >= 10 and error_rate > 0.2:
        alerts.append({"rule": "error_rate", "severity": "warning", "value": error_rate, "detail": f"{errors}/{calls} calls failed"})
    if calls >= 10 and p95_latency > 30000:
        alerts.append({"rule": "p95_latency", "severity": "warning", "value": p95_latency, "detail": f"p95 latency {p95_latency:.0f}ms"})
    if int(summary.get("in_progress_count") or 0) > 0:
        alerts.append(
            {
                "rule": "unfinished_spans",
                "severity": "info",
                "value": int(summary.get("in_progress_count") or 0),
                "detail": "in-progress spans may indicate active work or crashed calls",
            }
        )
    return pd.DataFrame(alerts)


def load_eval_reports(database_url: str):
    query = text(
        """
        SELECT report_id::text, task_set_name, run_id_a, run_id_b, created_at, summary
        FROM eval_reports
        ORDER BY created_at DESC
        LIMIT 100
        """
    )
    return pd.read_sql(query, _engine(database_url))


def load_eval_task_results(database_url: str, report_id: str):
    query = text(
        """
        SELECT task_id, run_a_status, run_a_judge_score, run_b_status, run_b_judge_score, regressed, detail
        FROM eval_task_results
        WHERE report_id::text = :report_id
        ORDER BY task_id ASC
        """
    )
    return pd.read_sql(query, _engine(database_url), params={"report_id": report_id})

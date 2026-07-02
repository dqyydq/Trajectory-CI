from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text


def _engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def load_spans(database_url: str, *, trace_id: str | None, session_id: str | None, model: str | None, status: str | None):
    where = []
    params = {}
    if trace_id:
        where.append("s.trace_id::text = :trace_id")
        params["trace_id"] = trace_id
    if session_id:
        where.append("t.session_id = :session_id")
        params["session_id"] = session_id
    if model:
        where.append("s.model = :model")
        params["model"] = model
    if status:
        where.append("s.status = :status")
        params["status"] = status
    clause = "WHERE " + " AND ".join(where) if where else ""
    query = text(
        f"""
        SELECT s.span_id::text, s.trace_id::text, t.session_id, s.parent_span_id::text,
               s.model, s.status, s.is_stream, s.prompt_tokens, s.completion_tokens,
               s.total_tokens, s.cost_usd, s.latency_ms, s.started_at, s.ended_at
        FROM spans s
        JOIN traces t ON t.trace_id = s.trace_id
        {clause}
        ORDER BY s.started_at DESC
        LIMIT 200
        """
    )
    return pd.read_sql(query, _engine(database_url), params=params)


def load_trace_spans(database_url: str, trace_id: str):
    query = text(
        """
        SELECT span_id::text, parent_span_id::text, model, status, latency_ms,
               prompt_tokens, completion_tokens, total_tokens, cost_usd, started_at, ended_at
        FROM spans
        WHERE trace_id::text = :trace_id
        ORDER BY started_at ASC
        """
    )
    return pd.read_sql(query, _engine(database_url), params={"trace_id": trace_id})


def load_cost_trend(database_url: str):
    query = text(
        """
        SELECT date_trunc('hour', started_at) AS hour,
               count(*) AS call_count,
               coalesce(sum(cost_usd), 0) AS cost_usd
        FROM spans
        WHERE status IN ('success', 'error')
        GROUP BY 1
        ORDER BY 1
        """
    )
    return pd.read_sql(query, _engine(database_url))

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

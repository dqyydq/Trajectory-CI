from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from app.core.config import settings
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
from dashboard.tree import span_tree_rows

st.set_page_config(page_title="Agent Observability Gateway", layout="wide", initial_sidebar_state="expanded")


def _css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700;800&display=swap');
        :root {
            --bg: #090b0f;
            --panel: rgba(255, 255, 255, 0.055);
            --panel-strong: rgba(255, 255, 255, 0.095);
            --stroke: rgba(255, 255, 255, 0.13);
            --text: #f6f7fb;
            --muted: rgba(246, 247, 251, 0.62);
            --green: #6ee7b7;
            --cyan: #67e8f9;
            --red: #fb7185;
            --amber: #fbbf24;
        }
        html, body, [class*="css"] { font-family: 'Geist', sans-serif; }
        .stApp {
            color: var(--text);
            background:
                radial-gradient(circle at 15% 8%, rgba(103, 232, 249, 0.16), transparent 28%),
                radial-gradient(circle at 88% 20%, rgba(251, 113, 133, 0.12), transparent 24%),
                linear-gradient(145deg, #090b0f 0%, #111827 48%, #07080b 100%);
        }
        header[data-testid="stHeader"] { background: transparent; }
        section[data-testid="stSidebar"] {
            background: rgba(8, 10, 14, 0.88);
            border-right: 1px solid var(--stroke);
        }
        div[data-testid="stMetric"] {
            background: var(--panel);
            border: 1px solid var(--stroke);
            border-radius: 8px;
            padding: 18px 18px 14px;
            min-height: 118px;
            backdrop-filter: blur(20px);
            box-shadow: 0 18px 50px rgba(0,0,0,0.24);
        }
        div[data-testid="stMetric"] label { color: var(--muted) !important; font-weight: 600; }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--text); font-weight: 800; }
        .hero-shell {
            position: relative;
            overflow: hidden;
            border: 1px solid var(--stroke);
            border-radius: 10px;
            padding: 34px 38px;
            margin-bottom: 22px;
            background:
                linear-gradient(90deg, rgba(255,255,255,0.10), rgba(255,255,255,0.035)),
                url('https://picsum.photos/seed/observability-command-center/1920/1080');
            background-size: cover;
            background-position: center;
            box-shadow: inset 0 0 0 999px rgba(6, 8, 12, 0.62), 0 24px 80px rgba(0,0,0,0.32);
        }
        .hero-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.8fr);
            gap: 26px;
            align-items: end;
        }
        .hero-title {
            max-width: 1120px;
            margin: 0;
            font-size: clamp(44px, 5.2vw, 82px);
            line-height: 0.94;
            letter-spacing: 0;
            color: var(--text);
            font-weight: 800;
        }
        .hero-copy { max-width: 720px; margin-top: 18px; color: var(--muted); font-size: 17px; line-height: 1.6; }
        .hero-panel {
            background: rgba(7, 9, 13, 0.72);
            border: 1px solid var(--stroke);
            border-radius: 8px;
            padding: 20px;
        }
        .hero-panel strong { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: .12em; }
        .hero-panel code { color: var(--cyan); background: rgba(103, 232, 249, .10); padding: 2px 5px; border-radius: 4px; white-space: normal; overflow-wrap: anywhere; word-break: break-word; }
        .metric-card { background: var(--panel); border: 1px solid var(--stroke); border-radius: 8px; padding: 18px; min-height: 118px; box-shadow: 0 18px 50px rgba(0,0,0,0.24); }
        .metric-label { color: var(--muted); font-size: 13px; font-weight: 700; margin-bottom: 10px; }
        .metric-value { color: var(--text); font-size: clamp(28px, 3vw, 44px); line-height: 1; font-weight: 800; overflow-wrap: anywhere; }
        .metric-delta { color: var(--green); font-size: 13px; margin-top: 12px; }
        .section-title { font-size: 26px; font-weight: 800; margin: 20px 0 10px; color: var(--text); }
        .section-copy { color: var(--muted); margin: 0 0 18px; }
        .alert-card {
            border: 1px solid var(--stroke);
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 10px;
            background: var(--panel);
        }
        .alert-warning { border-color: rgba(251, 113, 133, .55); background: rgba(251, 113, 133, .10); }
        .alert-info { border-color: rgba(103, 232, 249, .45); background: rgba(103, 232, 249, .08); }
        .trace-row {
            border: 1px solid var(--stroke);
            border-radius: 8px;
            padding: 10px 12px;
            margin: 8px 0;
            background: rgba(255,255,255,.045);
        }
        .muted { color: var(--muted); }
        .status-success { color: var(--green); font-weight: 700; }
        .status-error { color: var(--red); font-weight: 700; }
        .status-in_progress { color: var(--amber); font-weight: 700; }
        @media (max-width: 900px) {
            .hero-grid { grid-template-columns: 1fr; }
            .hero-shell { padding: 26px 22px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _safe_float(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def _money(value: Any) -> str:
    return f"${_safe_float(value):,.4f}"


def _ms(value: Any) -> str:
    return f"{_safe_float(value):,.0f}ms"


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _status_class(status: str) -> str:
    return f"status-{status}"


def _render_trace_tree(trace_spans: pd.DataFrame) -> None:
    if trace_spans.empty:
        st.info("No spans found for this trace.")
        return
    for depth, row in span_tree_rows(trace_spans.to_dict("records")):
        indent = "&nbsp;" * depth * 6
        status = str(row.get("status") or "unknown")
        stream = "stream" if row.get("is_stream") else "sync"
        latency = _ms(row.get("latency_ms")) if row.get("latency_ms") is not None else "open"
        st.markdown(
            f"""
            <div class="trace-row">
              {indent}<code>{row['span_id']}</code>
              <span class="{_status_class(status)}">{status}</span>
              <span class="muted">{row.get('span_type', 'llm_call')} · {row.get('model') or 'unknown'} · {stream} · {latency} · {_money(row.get('cost_usd'))}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander(f"Payload {row['span_id']}", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.caption("request")
                st.json(row.get("request_body"), expanded=False)
            with c2:
                st.caption("response")
                st.json(row.get("response_body"), expanded=False)
            if row.get("error_message"):
                st.error(row.get("error_message"))


_css()

options = load_filter_options(settings.dashboard_database_url)

with st.sidebar:
    st.markdown("### Command filters")
    hours = st.select_slider("time window", options=[1, 6, 12, 24, 72, 168], value=24, format_func=lambda h: f"{h}h")
    tenant_options = [""] + list(options.get("tenants", []))
    model_options = [""] + list(options.get("models", []))
    tenant_id = st.selectbox("tenant", tenant_options, format_func=lambda value: value or "all tenants")
    model = st.selectbox("model", model_options, format_func=lambda value: value or "all models")
    status = st.selectbox("status", ["", "in_progress", "success", "error"], format_func=lambda value: value or "all statuses")
    trace_id = st.text_input("trace_id")
    session_id = st.text_input("session_id")
    auto_refresh = st.toggle("auto-refresh intent", value=False, help="Visual marker only; rerun manually from Streamlit controls.")

summary = load_health_summary(
    settings.dashboard_database_url,
    tenant_id=tenant_id or None,
    model=model or None,
    hours=hours,
)
call_count = int(summary.get("call_count") or 0)
error_count = int(summary.get("error_count") or 0)
error_rate = error_count / call_count if call_count else 0.0

st.markdown(
    f"""
    <div class="hero-shell">
      <div class="hero-grid">
        <div>
          <h1 class="hero-title">Operational visibility for agent calls.</h1>
          <p class="hero-copy">Track tenant health, failed spans, live cost, streaming behavior, and eval regressions from one dense command surface.</p>
        </div>
        <div class="hero-panel">
          <strong>Target</strong><br />
          <code>{settings.dashboard_database_url.split('@')[-1]}</code><br /><br />
          <span class="muted">Window {hours}h · tenant {tenant_id or 'all'} · model {model or 'all'} · refreshed {datetime.now().strftime('%H:%M:%S')}</span>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

def _metric_card(label: str, value: str, delta: str, tone: str = "") -> str:
    return f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value {tone}">{value}</div>
      <div class="metric-delta">{delta}</div>
    </div>
    """

m1, m2, m3, m4 = st.columns(4)
m1.markdown(_metric_card("Health", "Watch" if error_rate > 0.2 else "Nominal", _pct(error_rate), "status-error" if error_rate > 0.2 else "status-success"), unsafe_allow_html=True)
m2.markdown(_metric_card("Calls", f"{call_count:,}", f"{int(summary.get('trace_count') or 0):,} traces"), unsafe_allow_html=True)
m3.markdown(_metric_card("Cost", _money(summary.get("cost_usd")), f"{int(summary.get('total_tokens') or 0):,} tokens"), unsafe_allow_html=True)
m4.markdown(_metric_card("p95 latency", _ms(summary.get("p95_latency_ms")), f"avg {_ms(summary.get('avg_latency_ms'))}"), unsafe_allow_html=True)

left, right = st.columns([2, 1], gap="large")
with left:
    st.markdown('<div class="section-title">Cost and latency movement</div>', unsafe_allow_html=True)
    trend = load_cost_trend(settings.dashboard_database_url, tenant_id=tenant_id or None, model=model or None, hours=hours)
    if trend.empty:
        st.info("No completed calls in this window.")
    else:
        st.line_chart(trend, x="hour", y=["cost_usd", "call_count", "avg_latency_ms"], use_container_width=True)
with right:
    st.markdown('<div class="section-title">Live alert posture</div>', unsafe_allow_html=True)
    alerts = load_alert_snapshot(settings.dashboard_database_url, tenant_id=tenant_id or None, model=model or None, hours=hours)
    if alerts.empty:
        st.success("No dynamic alert conditions in this window.")
    else:
        for alert in alerts.to_dict("records"):
            klass = "alert-warning" if alert["severity"] == "warning" else "alert-info"
            st.markdown(
                f"<div class='alert-card {klass}'><strong>{alert['rule']}</strong><br><span class='muted'>{alert['detail']}</span></div>",
                unsafe_allow_html=True,
            )

tab_calls, tab_trace, tab_cost, tab_eval = st.tabs(["Calls", "Trace", "Cost", "Eval"])

with tab_calls:
    st.markdown('<div class="section-title">Recent call ledger</div>', unsafe_allow_html=True)
    spans = load_spans(
        settings.dashboard_database_url,
        trace_id=trace_id or None,
        session_id=session_id or None,
        tenant_id=tenant_id or None,
        model=model or None,
        status=status or None,
        hours=hours,
    )
    st.dataframe(spans, use_container_width=True, hide_index=True)

with tab_trace:
    st.markdown('<div class="section-title">Trace inspection</div>', unsafe_allow_html=True)
    selected_trace_id = st.text_input("Trace detail id", value=trace_id)
    if selected_trace_id:
        trace_spans = load_trace_spans(settings.dashboard_database_url, selected_trace_id)
        _render_trace_tree(trace_spans)
    else:
        st.info("Paste a trace_id in the sidebar or above to inspect the span tree.")

with tab_cost:
    st.markdown('<div class="section-title">Model economics</div>', unsafe_allow_html=True)
    breakdown = load_model_breakdown(settings.dashboard_database_url, tenant_id=tenant_id or None, hours=hours)
    if breakdown.empty:
        st.info("No model activity in this window.")
    else:
        st.dataframe(breakdown, use_container_width=True, hide_index=True)
        st.bar_chart(breakdown, x="model", y="cost_usd", use_container_width=True)

with tab_eval:
    st.markdown('<div class="section-title">Regression intelligence</div>', unsafe_allow_html=True)
    reports = load_eval_reports(settings.dashboard_database_url)
    if reports.empty:
        st.info("No eval reports yet.")
    else:
        labels = {
            f"{row.task_set_name}: {row.run_id_b} vs {row.run_id_a} ({row.created_at})": row.report_id
            for row in reports.itertuples()
        }
        selected_label = st.selectbox("Eval report", list(labels.keys()))
        selected_report_id = labels[selected_label]
        report = reports[reports["report_id"] == selected_report_id].iloc[0]
        summary_data = report["summary"] or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{report['run_id_a']} pass", f"{summary_data.get('run_a_pass_rate', 0):.2%}")
        c2.metric(f"{report['run_id_b']} pass", f"{summary_data.get('run_b_pass_rate', 0):.2%}")
        c3.metric("Regressions", summary_data.get("regressed_count", 0))
        c4.metric("Tasks", summary_data.get("task_count", 0))

        task_results = load_eval_task_results(settings.dashboard_database_url, selected_report_id)
        display = task_results.drop(columns=["detail"]).copy()
        st.dataframe(
            display.style.apply(lambda row: ["background-color: rgba(251, 113, 133, 0.20)" if row.get("regressed") else "" for _ in row], axis=1),
            use_container_width=True,
            hide_index=True,
        )

        task_ids = task_results["task_id"].tolist()
        selected_task = st.selectbox("Task detail", task_ids)
        detail = task_results[task_results["task_id"] == selected_task].iloc[0]["detail"]
        st.json(detail)
        for side in ["run_a", "run_b"]:
            st.subheader(side)
            for trace in detail.get(side, {}).get("trace_ids", []):
                with st.expander(f"Trace {trace}"):
                    _render_trace_tree(load_trace_spans(settings.dashboard_database_url, trace))

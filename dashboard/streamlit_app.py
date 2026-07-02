from __future__ import annotations

import streamlit as st

from app.core.config import settings
from dashboard.queries import load_cost_trend, load_eval_reports, load_eval_task_results, load_spans, load_trace_spans
from dashboard.tree import span_tree_rows

st.set_page_config(page_title="Agent Observability Gateway", layout="wide")
st.title("Agent Observability Gateway")

with st.sidebar:
    trace_id = st.text_input("trace_id")
    session_id = st.text_input("session_id")
    model = st.text_input("model")
    status = st.selectbox("status", ["", "in_progress", "success", "error"])

tab_calls, tab_trace, tab_cost, tab_eval = st.tabs(["Calls", "Trace", "Cost", "Eval"])

with tab_calls:
    spans = load_spans(
        settings.dashboard_database_url,
        trace_id=trace_id or None,
        session_id=session_id or None,
        model=model or None,
        status=status or None,
    )
    st.dataframe(spans, use_container_width=True, hide_index=True)

with tab_trace:
    selected_trace_id = st.text_input("Trace detail id", value=trace_id)
    if selected_trace_id:
        trace_spans = load_trace_spans(settings.dashboard_database_url, selected_trace_id)
        for depth, row in span_tree_rows(trace_spans.to_dict("records")):
            indent = "&nbsp;" * depth * 4
            st.markdown(
                f"{indent}- `{row['span_id']}` {row['model']} "
                f"**{row['status']}** {row['latency_ms']}ms ${row['cost_usd'] or 0}"
            )

with tab_cost:
    trend = load_cost_trend(settings.dashboard_database_url)
    if trend.empty:
        st.info("No completed calls yet.")
    else:
        st.line_chart(trend, x="hour", y=["cost_usd", "call_count"])

with tab_eval:
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
        summary = report["summary"] or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{report['run_id_a']} pass", f"{summary.get('run_a_pass_rate', 0):.2%}")
        c2.metric(f"{report['run_id_b']} pass", f"{summary.get('run_b_pass_rate', 0):.2%}")
        c3.metric("Regressions", summary.get("regressed_count", 0))
        c4.metric("Tasks", summary.get("task_count", 0))

        task_results = load_eval_task_results(settings.dashboard_database_url, selected_report_id)
        display = task_results.drop(columns=["detail"]).copy()
        st.dataframe(
            display.style.apply(lambda row: ["background-color: #ffd6d6" if row.get("regressed") else "" for _ in row], axis=1),
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
                    trace_spans = load_trace_spans(settings.dashboard_database_url, trace)
                    for depth, row in span_tree_rows(trace_spans.to_dict("records")):
                        indent = "&nbsp;" * depth * 4
                        st.markdown(
                            f"{indent}- `{row['span_id']}` {row['model']} "
                            f"**{row['status']}** {row['latency_ms']}ms ${row['cost_usd'] or 0}"
                        )
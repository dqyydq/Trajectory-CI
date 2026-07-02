from __future__ import annotations

import streamlit as st

from app.core.config import settings
from dashboard.queries import load_cost_trend, load_spans, load_trace_spans
from dashboard.tree import span_tree_rows

st.set_page_config(page_title="Agent Observability Gateway", layout="wide")
st.title("Agent Observability Gateway")

with st.sidebar:
    trace_id = st.text_input("trace_id")
    session_id = st.text_input("session_id")
    model = st.text_input("model")
    status = st.selectbox("status", ["", "in_progress", "success", "error"])

tab_calls, tab_trace, tab_cost = st.tabs(["Calls", "Trace", "Cost"])

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


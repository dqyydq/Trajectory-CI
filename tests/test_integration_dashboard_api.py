from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
from fastapi.testclient import TestClient

from app.api import dashboard as dashboard_api
from app.main import app


def test_dashboard_summary_serializes_decimal_and_timestamp(monkeypatch) -> None:
    def fake_summary(database_url, *, tenant_id, model, hours):
        assert tenant_id == "tenant-a"
        assert model == "model-a"
        assert hours == 6
        return {
            "call_count": 2,
            "cost_usd": Decimal("0.125000"),
            "generated_at": pd.Timestamp(datetime(2026, 7, 2, tzinfo=UTC)),
        }

    monkeypatch.setattr(dashboard_api, "load_health_summary", fake_summary)

    with TestClient(app) as client:
        response = client.get("/api/dashboard/summary?tenant_id=tenant-a&model=model-a&hours=6")

    assert response.status_code == 200
    assert response.json() == {
        "call_count": 2,
        "cost_usd": 0.125,
        "generated_at": "2026-07-02T00:00:00+00:00",
    }


def test_dashboard_spans_returns_records(monkeypatch) -> None:
    def fake_spans(database_url, **kwargs):
        assert kwargs["status"] == "success"
        return pd.DataFrame(
            [
                {
                    "span_id": "span-a",
                    "trace_id": "trace-a",
                    "tenant_id": "tenant-a",
                    "status": "success",
                    "cost_usd": Decimal("0.000001"),
                }
            ]
        )

    monkeypatch.setattr(dashboard_api, "load_spans", fake_spans)

    with TestClient(app) as client:
        response = client.get("/api/dashboard/spans?status=success")

    assert response.status_code == 200
    assert response.json() == [
        {
            "span_id": "span-a",
            "trace_id": "trace-a",
            "tenant_id": "tenant-a",
            "status": "success",
            "cost_usd": 0.000001,
        }
    ]


def test_dashboard_filters_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(dashboard_api, "load_filter_options", lambda database_url: {"tenants": ["default"], "models": ["gpt-test"]})

    with TestClient(app) as client:
        response = client.get("/api/dashboard/filters")

    assert response.status_code == 200
    assert response.json() == {"tenants": ["default"], "models": ["gpt-test"]}
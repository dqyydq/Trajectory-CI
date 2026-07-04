from __future__ import annotations

from app.db.models import EvalTaskStatus
from eval.schemas import GateFailure, GateResult, RegressionGate, TaskComparisonDetail


def _pct_delta(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None or previous <= 0:
        return None
    return round(((current - previous) / previous) * 100, 4)


def build_gate_result(*, gate: RegressionGate | None, details: dict[str, TaskComparisonDetail], summary: dict) -> GateResult:
    rules = (gate or RegressionGate()).model_dump(mode="json")
    failures: list[GateFailure] = []

    regressed_count = int(summary.get("regressed_count") or 0)
    failed_count = int(summary.get("run_b_failed_count") or 0)
    not_run_count = int(summary.get("run_b_not_run_count") or 0)
    cost_delta = summary.get("cost_delta_pct")
    latency_delta = summary.get("latency_delta_pct")

    checks: list[tuple[str, int | float | None, int | float | None, str]] = [
        ("max_regressed_tasks", regressed_count, gate.max_regressed_tasks if gate else 0, "regressed tasks"),
        ("max_failed_tasks", failed_count, gate.max_failed_tasks if gate else 0, "failed candidate tasks"),
        ("max_not_run_tasks", not_run_count, gate.max_not_run_tasks if gate else 0, "not-run candidate tasks"),
        ("max_cost_increase_pct", cost_delta, gate.max_cost_increase_pct if gate else None, "cost increase"),
        ("max_latency_increase_pct", latency_delta, gate.max_latency_increase_pct if gate else None, "latency increase"),
    ]
    for rule, actual, limit, label in checks:
        if actual is None or limit is None:
            continue
        if actual > limit:
            failures.append(
                GateFailure(
                    rule=rule,
                    actual=actual,
                    limit=limit,
                    message=f"{label} {actual} exceeded allowed {limit}",
                )
            )

    return GateResult(status="failed" if failures else "passed", failures=failures, rules=rules, configured=gate is not None)


def summarize_gate_inputs(*, details: dict[str, TaskComparisonDetail], run_a_results, run_b_results) -> dict:
    run_a_cost = round(sum(run.cost_usd for run in run_a_results), 6)
    run_b_cost = round(sum(run.cost_usd for run in run_b_results), 6)
    run_a_latencies = [run.avg_latency_ms for run in run_a_results if run.avg_latency_ms is not None]
    run_b_latencies = [run.avg_latency_ms for run in run_b_results if run.avg_latency_ms is not None]
    run_a_latency = round(sum(run_a_latencies) / len(run_a_latencies), 2) if run_a_latencies else None
    run_b_latency = round(sum(run_b_latencies) / len(run_b_latencies), 2) if run_b_latencies else None
    failed_statuses = {EvalTaskStatus.hard_check_failed.value, EvalTaskStatus.judge_failed.value}

    return {
        "run_a_cost_usd": run_a_cost,
        "run_b_cost_usd": run_b_cost,
        "cost_delta_pct": _pct_delta(run_a_cost, run_b_cost),
        "run_a_avg_latency_ms": run_a_latency,
        "run_b_avg_latency_ms": run_b_latency,
        "latency_delta_pct": _pct_delta(run_a_latency, run_b_latency),
        "run_b_failed_count": sum(1 for run in run_b_results if run.status in failed_statuses),
        "run_b_not_run_count": sum(1 for run in run_b_results if run.status == EvalTaskStatus.not_run.value),
    }

from eval.compare.gate import build_gate_result, summarize_gate_inputs
from eval.schemas import JudgeResult, RegressionGate, RunEvaluation, TaskComparisonDetail, TaskDiff


def _detail(regressed: bool = False) -> TaskComparisonDetail:
    return TaskComparisonDetail(
        run_a=RunEvaluation(run_id="baseline", status="judged", judge=JudgeResult(score=4, reason="ok"), cost_usd=1, avg_latency_ms=100),
        run_b=RunEvaluation(run_id="candidate", status="judged", judge=JudgeResult(score=3, reason="worse"), cost_usd=1.25, avg_latency_ms=130),
        diff=TaskDiff(regressed=regressed, reason="score decreased", score_delta=-1, status_change="judged_to_judged"),
    )


def test_gate_fails_on_regression_and_cost_delta() -> None:
    detail = _detail(regressed=True)
    summary = {
        "regressed_count": 1,
        "run_b_failed_count": 0,
        "run_b_not_run_count": 0,
        "cost_delta_pct": 25.0,
        "latency_delta_pct": 30.0,
    }

    result = build_gate_result(
        gate=RegressionGate(max_regressed_tasks=0, max_cost_increase_pct=15, max_latency_increase_pct=20),
        details={"task-a": detail},
        summary=summary,
    )

    assert result.status == "failed"
    assert [failure.rule for failure in result.failures] == [
        "max_regressed_tasks",
        "max_cost_increase_pct",
        "max_latency_increase_pct",
    ]


def test_summarize_gate_inputs_computes_ci_metrics() -> None:
    run_a = [RunEvaluation(run_id="a", status="judged", cost_usd=0.1, avg_latency_ms=100)]
    run_b = [RunEvaluation(run_id="b", status="not_run", cost_usd=0.2, avg_latency_ms=150)]

    summary = summarize_gate_inputs(details={}, run_a_results=run_a, run_b_results=run_b)

    assert summary["run_a_cost_usd"] == 0.1
    assert summary["run_b_cost_usd"] == 0.2
    assert summary["cost_delta_pct"] == 100.0
    assert summary["latency_delta_pct"] == 50.0
    assert summary["run_b_not_run_count"] == 1

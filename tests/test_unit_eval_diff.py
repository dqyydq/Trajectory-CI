from eval.compare.diff import calculate_task_diff
from eval.schemas import JudgeResult, RunEvaluation


def test_diff_detects_not_run_regression() -> None:
    run_a = RunEvaluation(run_id="v1", status="judged", judge=JudgeResult(score=4, reason="ok"))
    run_b = RunEvaluation(run_id="v2", status="not_run")

    diff = calculate_task_diff(run_a, run_b)

    assert diff.regressed is True
    assert diff.status_change == "judged_to_not_run"


def test_diff_detects_score_drop() -> None:
    run_a = RunEvaluation(run_id="v1", status="judged", judge=JudgeResult(score=4.5, reason="good"))
    run_b = RunEvaluation(run_id="v2", status="judged", judge=JudgeResult(score=3.5, reason="worse"))

    diff = calculate_task_diff(run_a, run_b)

    assert diff.regressed is True
    assert diff.score_delta == -1.0


def test_diff_allows_improvement() -> None:
    run_a = RunEvaluation(run_id="v1", status="hard_check_failed")
    run_b = RunEvaluation(run_id="v2", status="judged", judge=JudgeResult(score=4, reason="better"))

    diff = calculate_task_diff(run_a, run_b)

    assert diff.regressed is False
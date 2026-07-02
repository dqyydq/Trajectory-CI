from __future__ import annotations

from eval.schemas import RunEvaluation, TaskComparisonDetail, TaskDiff

REGRESSION_SCORE_THRESHOLD = -0.5


STATUS_RANK = {
    "not_run": 0,
    "hard_check_failed": 1,
    "judge_failed": 2,
    "judged": 3,
}


def calculate_task_diff(run_a: RunEvaluation, run_b: RunEvaluation, *, score_threshold: float = REGRESSION_SCORE_THRESHOLD) -> TaskDiff:
    status_change = f"{run_a.status}_to_{run_b.status}"
    rank_a = STATUS_RANK.get(run_a.status, 0)
    rank_b = STATUS_RANK.get(run_b.status, 0)

    score_delta = None
    if run_a.judge is not None and run_b.judge is not None:
        score_delta = round(run_b.judge.score - run_a.judge.score, 4)

    if rank_b < rank_a:
        return TaskDiff(
            regressed=True,
            reason=f"status regressed from {run_a.status} to {run_b.status}",
            score_delta=score_delta,
            status_change=status_change,
        )

    if score_delta is not None and score_delta < score_threshold:
        return TaskDiff(
            regressed=True,
            reason=f"judge score decreased by {abs(score_delta):.2f}",
            score_delta=score_delta,
            status_change=status_change,
        )

    return TaskDiff(
        regressed=False,
        reason="no regression detected",
        score_delta=score_delta,
        status_change=status_change,
    )


def build_detail(run_a: RunEvaluation, run_b: RunEvaluation) -> TaskComparisonDetail:
    return TaskComparisonDetail(run_a=run_a, run_b=run_b, diff=calculate_task_diff(run_a, run_b))
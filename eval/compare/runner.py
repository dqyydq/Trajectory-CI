from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvalTaskStatus
from eval.checks.registry import run_checks
from eval.compare.diff import build_detail
from eval.compare.report import export_markdown, persist_report
from eval.data_fetcher import FetchedTrajectory, fetch_trajectory
from eval.loader import load_task_set
from eval.schemas import EvalTask, JudgeResult, RunEvaluation, TaskComparisonDetail


class Scorer(Protocol):
    def score(self, *, task: EvalTask, trajectory: FetchedTrajectory) -> JudgeResult: ...


@dataclass(frozen=True)
class CompareResult:
    report_id: str | None
    summary: dict
    details: dict[str, TaskComparisonDetail]


def _passed(status: str) -> bool:
    return status == EvalTaskStatus.judged.value


def _average_score(runs: list[RunEvaluation]) -> float | None:
    scores = [run.judge.score for run in runs if run.judge is not None]
    if not scores:
        return None
    return round(mean(scores), 4)


async def evaluate_run(
    *,
    session: AsyncSession,
    task: EvalTask,
    run_id: str,
    scorer: Scorer | None,
    skip_judge: bool,
) -> RunEvaluation:
    trajectory = await fetch_trajectory(session, task_id=task.task_id, run_id=run_id)
    if not trajectory.was_run:
        return RunEvaluation(run_id=run_id, status=EvalTaskStatus.not_run.value, trace_ids=[])

    check_results = run_checks(task.checks, trajectory)
    if any(not result.passed for result in check_results):
        return RunEvaluation(
            run_id=run_id,
            status=EvalTaskStatus.hard_check_failed.value,
            trace_ids=trajectory.trace_ids,
            check_results=check_results,
        )

    if skip_judge:
        return RunEvaluation(
            run_id=run_id,
            status=EvalTaskStatus.judged.value,
            trace_ids=trajectory.trace_ids,
            check_results=check_results,
            judge=JudgeResult(score=0, reason="judge skipped"),
        )

    if scorer is None:
        raise ValueError("scorer is required unless skip_judge=True")

    try:
        judge = scorer.score(task=task, trajectory=trajectory)
    except Exception as exc:
        return RunEvaluation(
            run_id=run_id,
            status=EvalTaskStatus.judge_failed.value,
            trace_ids=trajectory.trace_ids,
            check_results=check_results,
            judge=None,
        )

    return RunEvaluation(
        run_id=run_id,
        status=EvalTaskStatus.judged.value,
        trace_ids=trajectory.trace_ids,
        check_results=check_results,
        judge=judge,
    )


async def compare_runs(
    *,
    session: AsyncSession,
    task_set_path: str,
    task_set_name: str,
    run_id_b: str,
    run_id_a: str,
    scorer: Scorer | None,
    skip_judge: bool = False,
    export_markdown_path: str | None = None,
) -> CompareResult:
    task_set = load_task_set(task_set_path)
    details: dict[str, TaskComparisonDetail] = {}
    run_a_results: list[RunEvaluation] = []
    run_b_results: list[RunEvaluation] = []

    for task in task_set.tasks:
        run_a = await evaluate_run(session=session, task=task, run_id=run_id_a, scorer=scorer, skip_judge=skip_judge)
        run_b = await evaluate_run(session=session, task=task, run_id=run_id_b, scorer=scorer, skip_judge=skip_judge)
        detail = build_detail(run_a, run_b)
        details[task.task_id] = detail
        run_a_results.append(run_a)
        run_b_results.append(run_b)

    summary = {
        "task_count": len(task_set.tasks),
        "run_a_pass_rate": sum(_passed(run.status) for run in run_a_results) / len(task_set.tasks) if task_set.tasks else 0,
        "run_b_pass_rate": sum(_passed(run.status) for run in run_b_results) / len(task_set.tasks) if task_set.tasks else 0,
        "run_a_average_score": _average_score(run_a_results),
        "run_b_average_score": _average_score(run_b_results),
        "regressed_count": sum(detail.diff.regressed for detail in details.values()),
    }
    report = await persist_report(
        session,
        task_set_name=task_set_name,
        run_id_a=run_id_a,
        run_id_b=run_id_b,
        details=details,
        summary=summary,
    )
    if export_markdown_path:
        export_markdown(
            export_markdown_path,
            task_set_name=task_set_name,
            run_id_a=run_id_a,
            run_id_b=run_id_b,
            details=details,
            summary=summary,
        )
    return CompareResult(report_id=str(report.report_id), summary=summary, details=details)
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvalReport, EvalTaskResult, EvalTaskStatus
from eval.schemas import TaskComparisonDetail


def _score(detail: TaskComparisonDetail, side: str) -> Decimal | None:
    judge = getattr(detail, side).judge
    if judge is None:
        return None
    return Decimal(str(judge.score)).quantize(Decimal("0.01"))


def _check_passed(detail: TaskComparisonDetail, side: str) -> bool | None:
    run = getattr(detail, side)
    if run.status == EvalTaskStatus.not_run.value:
        return None
    if not run.check_results:
        return True
    return all(check.passed for check in run.check_results)


async def persist_report(
    session: AsyncSession,
    *,
    task_set_name: str,
    run_id_a: str,
    run_id_b: str,
    details: dict[str, TaskComparisonDetail],
    summary: dict,
) -> EvalReport:
    report = EvalReport(task_set_name=task_set_name, run_id_a=run_id_a, run_id_b=run_id_b, summary=summary)
    session.add(report)
    await session.flush()
    for task_id, detail in details.items():
        session.add(
            EvalTaskResult(
                report_id=report.report_id,
                task_id=task_id,
                run_a_status=EvalTaskStatus(detail.run_a.status),
                run_b_status=EvalTaskStatus(detail.run_b.status),
                run_a_check_passed=_check_passed(detail, "run_a"),
                run_a_judge_score=_score(detail, "run_a"),
                run_b_check_passed=_check_passed(detail, "run_b"),
                run_b_judge_score=_score(detail, "run_b"),
                regressed=detail.diff.regressed,
                detail=detail.model_dump(mode="json"),
            )
        )
    await session.commit()
    await session.refresh(report)
    return report


def render_markdown(*, task_set_name: str, run_id_a: str, run_id_b: str, details: dict[str, TaskComparisonDetail], summary: dict) -> str:
    gate = summary.get("gate") or {"status": "unknown", "failures": []}
    lines = [
        f"# Eval Report: {task_set_name}",
        "",
        f"Compared `{run_id_b}` against `{run_id_a}`.",
        "",
        f"## Regression Gate: {str(gate.get('status', 'unknown')).upper()}",
        "",
    ]
    failures = gate.get("failures") or []
    if failures:
        lines.extend([f"- {failure.get('message', failure)}" for failure in failures])
    else:
        lines.append("- All gate rules passed.")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Run A pass rate: {summary['run_a_pass_rate']:.2%}",
            f"- Run B pass rate: {summary['run_b_pass_rate']:.2%}",
            f"- Run A average score: {summary['run_a_average_score']}",
            f"- Run B average score: {summary['run_b_average_score']}",
            f"- Regressed tasks: {summary['regressed_count']}",
            f"- Candidate failed tasks: {summary.get('run_b_failed_count', 0)}",
            f"- Candidate not-run tasks: {summary.get('run_b_not_run_count', 0)}",
            f"- Cost: `{run_id_a}` ${summary.get('run_a_cost_usd', 0):.6f} -> `{run_id_b}` ${summary.get('run_b_cost_usd', 0):.6f} ({summary.get('cost_delta_pct')}%)",
            f"- Avg latency: `{run_id_a}` {summary.get('run_a_avg_latency_ms')}ms -> `{run_id_b}` {summary.get('run_b_avg_latency_ms')}ms ({summary.get('latency_delta_pct')}%)",
            "",
            "## Task Diff",
            "",
        ]
    )
    for task_id, detail in details.items():
        lines.extend(
            [
                f"### {task_id}",
                "",
                f"- Status: `{detail.run_a.status}` -> `{detail.run_b.status}`",
                f"- Regressed: `{detail.diff.regressed}`",
                f"- Reason: {detail.diff.reason}",
                f"- Trace A: {', '.join(detail.run_a.trace_ids) or 'none'}",
                f"- Trace B: {', '.join(detail.run_b.trace_ids) or 'none'}",
                "",
            ]
        )
    return "\n".join(lines)


def export_markdown(path: str | Path, *, task_set_name: str, run_id_a: str, run_id_b: str, details: dict[str, TaskComparisonDetail], summary: dict) -> None:
    Path(path).write_text(
        render_markdown(task_set_name=task_set_name, run_id_a=run_id_a, run_id_b=run_id_b, details=details, summary=summary),
        encoding="utf-8",
    )

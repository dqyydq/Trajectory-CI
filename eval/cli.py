from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.db.session import AsyncSessionLocal
from eval.compare.runner import compare_runs
from eval.judge.scorer import JudgeScorer


def _task_set_path(name_or_path: str) -> tuple[str, str]:
    path = Path(name_or_path)
    if path.suffix:
        return path.stem, str(path)
    return name_or_path, str(Path("eval") / "task_sets" / f"{name_or_path}.yaml")


async def _compare(args: argparse.Namespace) -> int:
    task_set_name, task_set_path = _task_set_path(args.task_set)
    scorer = None if args.skip_judge else JudgeScorer(model=args.judge_model, base_url=args.gateway_base_url)
    async with AsyncSessionLocal() as session:
        result = await compare_runs(
            session=session,
            task_set_path=task_set_path,
            task_set_name=task_set_name,
            run_id_b=args.run_id,
            run_id_a=args.against,
            scorer=scorer,
            skip_judge=args.skip_judge,
            export_markdown_path=args.export_markdown,
        )
    gate_label = result.gate.status.upper()
    print(f"REGRESSION GATE: {gate_label}")
    for failure in result.gate.failures:
        print(f"- {failure.message}")
    print(f"Report: {result.report_id}")
    print(f"Tasks: {result.summary['task_count']}")
    print(f"Pass rate: {args.against}={result.summary['run_a_pass_rate']:.2%}, {args.run_id}={result.summary['run_b_pass_rate']:.2%}")
    print(f"Average score: {args.against}={result.summary['run_a_average_score']}, {args.run_id}={result.summary['run_b_average_score']}")
    print(f"Cost: {args.against}=${result.summary['run_a_cost_usd']:.6f}, {args.run_id}=${result.summary['run_b_cost_usd']:.6f}, delta={result.summary['cost_delta_pct']}")
    print(f"Latency: {args.against}={result.summary['run_a_avg_latency_ms']}ms, {args.run_id}={result.summary['run_b_avg_latency_ms']}ms, delta={result.summary['latency_delta_pct']}")
    regressed = [task_id for task_id, detail in result.details.items() if detail.diff.regressed]
    if regressed:
        print("Regressions:")
        for task_id in regressed:
            print(f"- {task_id}: {result.details[task_id].diff.reason}")
    else:
        print("Regressions: none")
    return 1 if result.gate.status == "failed" and not args.no_fail_on_gate else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m eval")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--task-set", required=True)
    compare.add_argument("--run-id", required=True, help="new run id")
    compare.add_argument("--against", required=True, help="baseline run id")
    compare.add_argument("--export-markdown")
    compare.add_argument("--skip-judge", action="store_true")
    compare.add_argument("--no-fail-on-gate", action="store_true", help="print gate failures but exit 0")
    compare.add_argument("--judge-model", default="deepseek-v4-flash")
    compare.add_argument("--gateway-base-url", default="http://127.0.0.1:8000/v1")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "compare":
        raise SystemExit(asyncio.run(_compare(args)))


if __name__ == "__main__":
    main()

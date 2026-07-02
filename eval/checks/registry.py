from __future__ import annotations

from typing import Any

from eval.checks.builtin import run_builtin_check
from eval.schemas import CheckResult, CheckSpec


def run_check(check: CheckSpec, trajectory: Any) -> CheckResult:
    return run_builtin_check(check, trajectory)


def run_checks(checks: list[CheckSpec], trajectory: Any) -> list[CheckResult]:
    return [run_check(check, trajectory) for check in checks]
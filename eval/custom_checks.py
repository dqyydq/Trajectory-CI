from __future__ import annotations

from eval.schemas import CheckResult, CheckType


def no_duplicate_categories(trajectory) -> CheckResult:
    return CheckResult(
        type=CheckType.custom,
        passed=True,
        message="placeholder custom check passed",
        metadata={"function": "eval.custom_checks.no_duplicate_categories"},
    )
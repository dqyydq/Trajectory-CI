from __future__ import annotations

import importlib
from typing import Any

from eval.schemas import CheckResult, CheckSpec, CheckType


def run_builtin_check(check: CheckSpec, trajectory: Any) -> CheckResult:
    if check.type == CheckType.tool_called:
        return tool_called(trajectory, check.tool_name or "")
    if check.type == CheckType.max_steps:
        return max_steps(trajectory, check.value or 0)
    if check.type == CheckType.response_contains:
        return response_contains(trajectory, check.keyword or "")
    if check.type == CheckType.custom:
        return custom_check(trajectory, check.function or "")
    return CheckResult(type=str(check.type), passed=False, message="unsupported check type")


def tool_called(trajectory: Any, tool_name: str) -> CheckResult:
    found = _contains_tool_name(_span_bodies(trajectory), tool_name)
    return CheckResult(
        type=CheckType.tool_called,
        passed=found,
        message=f"tool {tool_name!r} {'was called' if found else 'was not called'}",
        metadata={"tool_name": tool_name},
    )


def max_steps(trajectory: Any, value: int) -> CheckResult:
    count = len(getattr(trajectory, "spans", []))
    passed = count <= value
    return CheckResult(
        type=CheckType.max_steps,
        passed=passed,
        message=f"span count {count} {'<=' if passed else '>'} max_steps {value}",
        metadata={"value": value, "actual_steps": count},
    )


def response_contains(trajectory: Any, keyword: str) -> CheckResult:
    text = _response_text(trajectory)
    passed = keyword in text
    return CheckResult(
        type=CheckType.response_contains,
        passed=passed,
        message=f"keyword {keyword!r} {'found' if passed else 'not found'} in response text",
        metadata={"keyword": keyword},
    )


def custom_check(trajectory: Any, function_path: str) -> CheckResult:
    module_name, _, function_name = function_path.rpartition(".")
    if not module_name or not function_name:
        return CheckResult(type=CheckType.custom, passed=False, message=f"invalid custom function path: {function_path}")
    module = importlib.import_module(module_name)
    result = getattr(module, function_name)(trajectory)
    if isinstance(result, CheckResult):
        return result
    if isinstance(result, bool):
        return CheckResult(type=CheckType.custom, passed=result, message=function_path, metadata={"function": function_path})
    if isinstance(result, dict):
        return CheckResult(type=CheckType.custom, **result)
    return CheckResult(type=CheckType.custom, passed=False, message=f"custom check returned unsupported value: {type(result).__name__}")


def _span_bodies(trajectory: Any) -> list[Any]:
    bodies: list[Any] = []
    for span in getattr(trajectory, "spans", []):
        body = getattr(span, "response_body", None)
        if body is None and isinstance(span, dict):
            body = span.get("response_body")
        bodies.append(body)
    return bodies


def _contains_tool_name(value: Any, tool_name: str) -> bool:
    if isinstance(value, dict):
        if value.get("name") == tool_name:
            return True
        function = value.get("function")
        if isinstance(function, dict) and function.get("name") == tool_name:
            return True
        return any(_contains_tool_name(item, tool_name) for item in value.values())
    if isinstance(value, list):
        return any(_contains_tool_name(item, tool_name) for item in value)
    return False


def _response_text(trajectory: Any) -> str:
    parts: list[str] = []
    for body in _span_bodies(trajectory):
        _collect_text(body, parts)
    return "\n".join(parts)


def _collect_text(value: Any, parts: list[str]) -> None:
    if isinstance(value, dict):
        choices = value.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if isinstance(choice, dict):
                    message = choice.get("message") or {}
                    if isinstance(message, dict) and isinstance(message.get("content"), str):
                        parts.append(message["content"])
        for item in value.values():
            _collect_text(item, parts)
    elif isinstance(value, list):
        for item in value:
            _collect_text(item, parts)
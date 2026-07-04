from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, model_validator


class CheckType(str, Enum):
    tool_called = "tool_called"
    max_steps = "max_steps"
    response_contains = "response_contains"
    custom = "custom"


class CheckSpec(BaseModel):
    type: CheckType
    tool_name: str | None = None
    value: int | None = None
    keyword: str | None = None
    function: str | None = None

    @model_validator(mode="after")
    def validate_by_type(self) -> "CheckSpec":
        if self.type == CheckType.tool_called and not self.tool_name:
            raise ValueError("tool_called check requires tool_name")
        if self.type == CheckType.max_steps and self.value is None:
            raise ValueError("max_steps check requires value")
        if self.type == CheckType.max_steps and self.value is not None and self.value < 0:
            raise ValueError("max_steps value must be >= 0")
        if self.type == CheckType.response_contains and not self.keyword:
            raise ValueError("response_contains check requires keyword")
        if self.type == CheckType.custom and not self.function:
            raise ValueError("custom check requires function")
        return self


class RegressionGate(BaseModel):
    max_regressed_tasks: int | None = Field(default=0, ge=0)
    max_failed_tasks: int | None = Field(default=0, ge=0)
    max_not_run_tasks: int | None = Field(default=0, ge=0)
    max_cost_increase_pct: float | None = Field(default=None, ge=0)
    max_latency_increase_pct: float | None = Field(default=None, ge=0)


class EvalTask(BaseModel):
    task_id: Annotated[str, Field(min_length=1, max_length=255)]
    description: Annotated[str, Field(min_length=1)]
    input: Annotated[str, Field(min_length=1)]
    judge_rubric: str | None = None
    checks: list[CheckSpec] = Field(default_factory=list)


class TaskSet(BaseModel):
    tasks: list[EvalTask]
    gate: RegressionGate | None = None

    @model_validator(mode="after")
    def ensure_unique_task_ids(self) -> "TaskSet":
        task_ids = [task.task_id for task in self.tasks]
        duplicates = sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate task_id values: {duplicates}")
        return self


class CheckResult(BaseModel):
    type: CheckType | str
    passed: bool
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class JudgeResult(BaseModel):
    score: float
    reason: str


class RunEvaluation(BaseModel):
    run_id: str
    status: str
    trace_ids: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    avg_latency_ms: float | None = None
    check_results: list[CheckResult] = Field(default_factory=list)
    judge: JudgeResult | None = None


class TaskDiff(BaseModel):
    regressed: bool
    reason: str
    score_delta: float | None = None
    status_change: str


class TaskComparisonDetail(BaseModel):
    run_a: RunEvaluation
    run_b: RunEvaluation
    diff: TaskDiff


class GateFailure(BaseModel):
    rule: str
    actual: float | int
    limit: float | int
    message: str


class GateResult(BaseModel):
    status: str
    failures: list[GateFailure] = Field(default_factory=list)
    rules: dict[str, float | int | None] = Field(default_factory=dict)
    configured: bool = False

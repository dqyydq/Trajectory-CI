from pathlib import Path
from uuid import uuid4

import pytest

from eval.loader import TaskSetLoadError, load_task_set
from eval.schemas import CheckType, TaskSet


def test_task_set_schema_validates_checks() -> None:
    task_set = TaskSet.model_validate(
        {
            "tasks": [
                {
                    "task_id": "task-a",
                    "description": "desc",
                    "input": "input",
                    "checks": [{"type": "response_contains", "keyword": "done"}],
                }
            ]
        }
    )

    assert task_set.tasks[0].checks[0].type == CheckType.response_contains


def test_task_set_schema_rejects_missing_check_field() -> None:
    with pytest.raises(ValueError, match="response_contains check requires keyword"):
        TaskSet.model_validate(
            {
                "tasks": [
                    {
                        "task_id": "task-a",
                        "description": "desc",
                        "input": "input",
                        "checks": [{"type": "response_contains"}],
                    }
                ]
            }
        )


def test_loader_reports_task_id_for_invalid_task() -> None:
    temp_dir = Path(".test_tmp")
    temp_dir.mkdir(exist_ok=True)
    path = temp_dir / f"bad-{uuid4()}.yaml"
    path.write_text(
        """
tasks:
  - task_id: bad-task
    description: desc
    input: input
    checks:
      - type: tool_called
""",
        encoding="utf-8",
    )

    with pytest.raises(TaskSetLoadError) as exc:
        load_task_set(path)

    assert "task_id=bad-task" in str(exc.value)
    assert "tool_called check requires tool_name" in str(exc.value)
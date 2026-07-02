from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from eval.schemas import TaskSet


class TaskSetLoadError(ValueError):
    pass


def load_task_set(path: str | Path) -> TaskSet:
    task_set_path = Path(path)
    try:
        raw = yaml.safe_load(task_set_path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise TaskSetLoadError(f"Could not read task set {task_set_path}: {exc}") from exc

    try:
        return TaskSet.model_validate(raw)
    except ValidationError as exc:
        messages: list[str] = []
        tasks = raw.get("tasks") if isinstance(raw, dict) else None
        for error in exc.errors():
            loc = list(error.get("loc", ()))
            task_id = None
            if len(loc) >= 2 and loc[0] == "tasks" and isinstance(loc[1], int) and isinstance(tasks, list):
                task = tasks[loc[1]] if loc[1] < len(tasks) else None
                if isinstance(task, dict):
                    task_id = task.get("task_id")
            location = ".".join(str(item) for item in loc)
            prefix = f"task_id={task_id} " if task_id else ""
            messages.append(f"{prefix}{location}: {error.get('msg')}")
        detail = "\n".join(messages)
        raise TaskSetLoadError(f"Invalid task set {task_set_path}:\n{detail}") from exc
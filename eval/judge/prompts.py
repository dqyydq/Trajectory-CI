from __future__ import annotations

GENERAL_PROMPT = """You are evaluating an LLM agent trajectory. Return JSON with keys score and reason. Score from 1 to 5.

Task description:
{description}

Task input:
{task_input}

Final response / trajectory summary:
{trajectory_text}
"""

RUBRIC_PROMPT = """You are evaluating an LLM agent trajectory using the provided rubric. Return JSON with keys score and reason. Score from 1 to 5.

Task description:
{description}

Task input:
{task_input}

Rubric:
{rubric}

Final response / trajectory summary:
{trajectory_text}
"""


def build_judge_prompt(*, description: str, task_input: str, trajectory_text: str, rubric: str | None) -> str:
    if rubric:
        return RUBRIC_PROMPT.format(
            description=description,
            task_input=task_input,
            rubric=rubric,
            trajectory_text=trajectory_text,
        )
    return GENERAL_PROMPT.format(description=description, task_input=task_input, trajectory_text=trajectory_text)
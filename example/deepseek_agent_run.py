from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from eval.loader import load_task_set
from eval.schemas import EvalTask

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


LEGACY_TASKS = {
    "deepseek_hello": {
        "prompt": "Hello. Reply in one short sentence.",
    },
    "deepseek_reasoning": {
        "prompt": "In one short paragraph, explain why observability matters for LLM agents.",
    },
}

PROFILE_PROMPTS = {
    "baseline": """You are a senior AI agent engineer. Give concise but complete engineering answers. Preserve important caveats, tradeoffs, and concrete debugging evidence. When a release decision is involved, weigh quality, cost, latency, and regression risk together.""",
    "candidate": """You are optimizing for brevity and low token usage. Answer as briefly as possible. Prefer a short direct answer over caveats, detailed tradeoffs, or diagnostic evidence.""",
}


def load_project_env() -> None:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", encoding="utf-8-sig")


def task_set_path(name_or_path: str) -> tuple[str, Path]:
    path = Path(name_or_path)
    if path.suffix:
        return path.stem, path
    return name_or_path, Path("eval") / "task_sets" / f"{name_or_path}.yaml"


def load_tasks(task_set: str | None) -> tuple[str, list[EvalTask]]:
    if not task_set:
        tasks = [
            EvalTask(task_id=task_id, description=task_id, input=item["prompt"])
            for task_id, item in LEGACY_TASKS.items()
        ]
        return "deepseek_smoke", tasks
    name, path = task_set_path(task_set)
    loaded = load_task_set(path)
    return name, loaded.tasks


def system_prompt(args: argparse.Namespace) -> str:
    if args.system_prompt_file:
        return Path(args.system_prompt_file).read_text(encoding="utf-8").strip()
    return PROFILE_PROMPTS[args.profile]


def call_task(*, client: OpenAI, run_id: str, task_set_name: str, task: EvalTask, system: str, model: str) -> None:
    session_id = f"{task_set_name}:{task.task_id}:{run_id}"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": task.input},
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
        extra_headers={
            "X-Session-Id": session_id,
            "X-Eval-Task-Id": task.task_id,
            "X-Eval-Run-Id": run_id,
        },
    )
    content = response.choices[0].message.content or ""
    print(f"[{task.task_id}] {content.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real DeepSeek agent tasks through the local Trajectory CI gateway.")
    parser.add_argument("--run-id", required=True, help="Evaluation run id, for example baseline or candidate.")
    parser.add_argument("--task-set", help="Task set name or YAML path. Defaults to the legacy deepseek smoke tasks.")
    parser.add_argument("--profile", choices=sorted(PROFILE_PROMPTS), default="baseline")
    parser.add_argument("--system-prompt-file", help="Optional prompt file overriding --profile.")
    parser.add_argument("--gateway-base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default=os.getenv("MODEL_ID", "deepseek-v4-flash"))
    parser.add_argument("--task", help="Run only one task id from the selected task set.")
    args = parser.parse_args()

    load_project_env()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set. Put it in the project .env file.")

    task_set_name, tasks = load_tasks(args.task_set)
    if args.task:
        tasks = [task for task in tasks if task.task_id == args.task]
        if not tasks:
            raise ValueError(f"Task {args.task!r} not found in {task_set_name}")

    client = OpenAI(
        api_key=api_key,
        base_url=args.gateway_base_url,
        http_client=httpx.Client(trust_env=False),
    )

    prompt = system_prompt(args)
    print(f"Task set: {task_set_name}")
    print(f"Run id: {args.run_id}")
    print(f"Profile: {args.profile}")
    for task in tasks:
        call_task(client=client, run_id=args.run_id, task_set_name=task_set_name, task=task, system=prompt, model=args.model)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI


TASKS = {
    "deepseek_hello": {
        "prompt": "Hello. Reply in one short sentence.",
    },
    "deepseek_reasoning": {
        "prompt": "In one short paragraph, explain why observability matters for LLM agents.",
    },
}


def load_project_env() -> None:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")


def call_task(*, client: OpenAI, gateway_base_url: str, run_id: str, task_id: str, prompt: str) -> None:
    session_id = f"deepseek_smoke:{task_id}:{run_id}"
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": "You are a concise helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
        extra_headers={
            "X-Session-Id": session_id,
            "X-Eval-Task-Id": task_id,
            "X-Eval-Run-Id": run_id,
        },
    )
    content = response.choices[0].message.content or ""
    print(f"[{task_id}] {content.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DeepSeek smoke tasks through the local observability gateway.")
    parser.add_argument("--run-id", required=True, help="Evaluation run id, for example v1 or v2.")
    parser.add_argument("--gateway-base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--task", choices=sorted(TASKS), help="Run only one task.")
    args = parser.parse_args()

    load_project_env()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set. Put it in the project .env file.")

    client = OpenAI(
        api_key=api_key,
        base_url=args.gateway_base_url,
        http_client=httpx.Client(trust_env=False),
    )

    selected = {args.task: TASKS[args.task]} if args.task else TASKS
    for task_id, task in selected.items():
        call_task(
            client=client,
            gateway_base_url=args.gateway_base_url,
            run_id=args.run_id,
            task_id=task_id,
            prompt=task["prompt"],
        )


if __name__ == "__main__":
    main()
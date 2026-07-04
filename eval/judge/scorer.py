from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import httpx
from openai import OpenAI

from eval.judge.prompts import build_judge_prompt
from eval.schemas import EvalTask, JudgeResult

load_dotenv(Path(".env"), encoding="utf-8-sig")


def trajectory_text(trajectory: Any) -> str:
    parts: list[str] = []
    for span in getattr(trajectory, "spans", []):
        body = getattr(span, "response_body", None)
        if isinstance(body, dict):
            for choice in body.get("choices") or []:
                if isinstance(choice, dict):
                    message = choice.get("message") or {}
                    if isinstance(message, dict) and isinstance(message.get("content"), str):
                        parts.append(message["content"])
    return "\n".join(parts)


class JudgeScorer:
    def __init__(self, *, model: str = "deepseek-v4-flash", base_url: str = "http://127.0.0.1:8000/v1") -> None:
        self.model = model
        self.base_url = base_url

    def score(self, *, task: EvalTask, trajectory: Any) -> JudgeResult:
        api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or "gateway-local"
        client = OpenAI(api_key=api_key, base_url=self.base_url, http_client=httpx.Client(trust_env=False))
        prompt = build_judge_prompt(
            description=task.description,
            task_input=task.input,
            rubric=task.judge_rubric,
            trajectory_text=trajectory_text(trajectory),
        )
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            extra_headers={"X-Span-Type": "llm_judge", "X-Session-Id": f"judge:{task.task_id}"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            match = re.search(r"\{[\s\S]*\}", content)
            parsed = json.loads(match.group(0) if match else content)
            return JudgeResult(score=float(parsed["score"]), reason=str(parsed["reason"]))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Judge returned invalid JSON: {content}") from exc

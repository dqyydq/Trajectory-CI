"""
mock_upstream_server.py

一个假的 OpenAI 兼容上游服务器，专门用来配合本地测试 Phase 1 网关。
不需要真实 OpenAI API Key，不产生任何费用。

核心机制：
- 正常情况下返回一个通用的假回复
- 如果请求的 messages 里，某条 message 的 content 以 "MOCK_RESPONSE:" 开头，
  后面跟一段 JSON（格式见下方 MockResponseSpec），服务器会按这段 JSON 的内容
  精确构造返回结果（包括自定义 content、是否带 tool_calls）。
  这样 simulate_agent_run.py 就能完全控制每一步"agent"的行为，不需要真的调用LLM。
- 如果检测到请求内容里包含 "score" 或 "评分" 关键词（用于粗略识别这是 judge 打分请求），
  会返回一段包含 JSON 打分结果的内容，方便你联调 judge 模块。这是个启发式判断，
  如果和你实际的 judge prompt 对不上，直接改 judge_heuristic_response() 这个函数即可。

用法：
    pip install fastapi uvicorn
    python mock_upstream_server.py
    # 默认监听 http://localhost:9000

然后把你 Phase 1 网关里"转发到真实 OpenAI"的那个 base_url 配置，
临时改成 http://localhost:9000 即可（具体是哪个环境变量/配置项，
去看你自己 app/core/config.py 或 app/proxy/openai_client.py 里
上游地址是怎么定义的）。
"""

import json
import time
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="mock-openai-upstream")


def fake_token_count(text: str) -> int:
    # 粗略估算，测试用，不追求精确
    return max(1, len(text) // 4)


def extract_mock_spec(messages: list[dict]) -> dict[str, Any] | None:
    """从请求消息里找有没有 MOCK_RESPONSE: 标记，有的话解析出精确响应规格"""
    for msg in messages:
        content = msg.get("content") or ""
        if isinstance(content, str) and content.startswith("MOCK_RESPONSE:"):
            raw = content[len("MOCK_RESPONSE:") :].strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
    return None


def looks_like_judge_request(messages: list[dict]) -> bool:
    joined = " ".join(str(m.get("content") or "") for m in messages).lower()
    return "score" in joined or "评分" in joined or "judge" in joined


def judge_heuristic_response() -> str:
    # 返回一段"看起来像"评分结果的 JSON 文本，供 judge/scorer.py 联调用。
    # 如果你的 scorer.py 期望的字段名不一样，改这里的 key 即可。
    return json.dumps(
        {"score": 4, "reasoning": "mock打分：整体质量尚可，符合基本任务要求（本结果由 mock upstream 生成，非真实评分）"},
        ensure_ascii=False,
    )


def build_message(spec: dict | None, messages: list[dict]) -> dict[str, Any]:
    if spec is not None:
        message: dict[str, Any] = {"role": "assistant", "content": spec.get("content", "")}
        if spec.get("tool_calls"):
            message["tool_calls"] = spec["tool_calls"]
            message["content"] = spec.get("content")  # OpenAI格式里带tool_calls时content可为null，这里保留原值
        return message

    if looks_like_judge_request(messages):
        return {"role": "assistant", "content": judge_heuristic_response()}

    return {"role": "assistant", "content": "这是一条默认的mock回复，用于本地测试。"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "gpt-4o-mini")
    is_stream = bool(body.get("stream", False))
    include_usage = bool(body.get("stream_options", {}).get("include_usage", False))

    spec = extract_mock_spec(messages)
    message = build_message(spec, messages)

    prompt_text = " ".join(str(m.get("content") or "") for m in messages)
    completion_text = message.get("content") or ""
    prompt_tokens = fake_token_count(prompt_text)
    completion_tokens = fake_token_count(completion_text)
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }

    completion_id = f"chatcmpl-mock-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    if not is_stream:
        response_body = {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                }
            ],
            "usage": usage,
        }
        return JSONResponse(response_body)

    # ---- streaming 分支 ----
    async def event_stream():
        role_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(role_chunk, ensure_ascii=False)}\n\n"

        text = completion_text or ""
        chunk_size = max(1, len(text) // 5) if text else 0
        pos = 0
        if text:
            while pos < len(text):
                piece = text[pos : pos + chunk_size]
                pos += chunk_size
                content_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(content_chunk, ensure_ascii=False)}\n\n"

        if message.get("tool_calls"):
            tool_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": message["tool_calls"]},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(tool_chunk, ensure_ascii=False)}\n\n"

        finish_chunk: dict[str, Any] = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                }
            ],
        }
        if include_usage:
            finish_chunk["usage"] = usage
        yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock-openai-upstream"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)

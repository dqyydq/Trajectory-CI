"""
simulate_agent_run.py

模拟一个"agent"去调用你的 Phase 1 网关，产生带 X-Eval-Task-Id / X-Eval-Run-Id 标签的
trace 数据，用于在没有真实 agent 的情况下测试 Phase 2 的 compare 流程。

内置三种场景（--scenario 参数）：
  baseline    模拟一个表现良好的版本：两个任务都在合理步数内完成，内容符合硬性检查
  regression  模拟一个变差的版本：classify_basic 任务步数超过 max_steps=8 阈值，
              应该被硬性检查拦下，触发"回归"
  partial     模拟一次没跑完的评测：只跑了 classify_basic，没跑 handle_empty_folder，
              用来验证 compare 时对 not_run 情况的处理

对应你 Phase 2 提示词里示例任务集 eval/task_sets/bilibili_agent_v1.yaml 的两个任务：
  - classify_basic      要求：调用 classify_video 工具 / 步数<=8 / 回复包含"分类完成"
  - handle_empty_folder  要求：回复包含"没有内容"

用法示例：
    python simulate_agent_run.py --run-id v1 --scenario baseline
    python simulate_agent_run.py --run-id v2 --scenario regression
    python simulate_agent_run.py --run-id v3 --scenario partial

跑完两次（比如 v1 baseline 和 v2 regression）之后，就可以执行：
    python -m eval compare --task-set bilibili_agent_v1 --run-id v2 --against v1
去验证 compare 流程能不能正确识别出 classify_basic 这个任务的回归。

注意：
- 默认假设 Phase 1 网关跑在 http://localhost:8000，OpenAI 兼容接口路径是 /v1/chat/completions，
  用 --gateway-url 可以改。
- 假设 Phase 1 用 X-Session-Id 这个 header 来把同一个任务内的多次调用关联成一个 trace
  （对应你们之前讨论的"相同 session_id 复用同一个 trace"设计）；如果你实际的 header 名字不是这个，
  改下面 SESSION_HEADER 常量即可。
- 需要真实调用时把 OPENAI_API_KEY 环境变量设个假值就行（比如 export OPENAI_API_KEY=sk-fake-for-testing），
  因为请求会经过网关，网关如果强制校验 Authorization header 格式，这样能避免报错；
  真正处理请求的是 mock_upstream_server.py，不会真的校验这个 key。
"""

import argparse
import json
import os

import httpx

GATEWAY_CHAT_PATH = "/v1/chat/completions"
SESSION_HEADER = "X-Session-Id"
TASK_ID_HEADER = "X-Eval-Task-Id"
RUN_ID_HEADER = "X-Eval-Run-Id"

FAKE_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-fake-for-testing")


def call_gateway(
    gateway_url: str,
    session_id: str,
    task_id: str,
    run_id: str,
    mock_content: str | None,
    mock_tool_calls: list[dict] | None,
    step_label: str,
) -> None:
    """发一次请求给网关，用 MOCK_RESPONSE 标记告诉 mock upstream 该怎么回复"""
    spec = {"content": mock_content}
    if mock_tool_calls:
        spec["tool_calls"] = mock_tool_calls

    messages = [
        {"role": "system", "content": f"MOCK_RESPONSE:{json.dumps(spec, ensure_ascii=False)}"},
        {"role": "user", "content": f"[{step_label}] 模拟任务步骤"},
    ]

    headers = {
        "Authorization": f"Bearer {FAKE_API_KEY}",
        SESSION_HEADER: session_id,
        TASK_ID_HEADER: task_id,
        RUN_ID_HEADER: run_id,
    }

    resp = httpx.post(
        f"{gateway_url}{GATEWAY_CHAT_PATH}",
        json={"model": "gpt-4o-mini", "messages": messages, "stream": False},
        headers=headers,
        timeout=30.0,
    )
    resp.raise_for_status()
    print(f"  [{task_id}] {step_label} -> status={resp.status_code}")


def run_classify_basic(gateway_url: str, run_id: str, steps: int, call_tool: bool, final_response: str) -> None:
    task_id = "classify_basic"
    session_id = f"{run_id}-{task_id}"
    print(f"运行任务 {task_id} (run_id={run_id}, 计划步数={steps})")

    for i in range(1, steps + 1):
        is_last = i == steps
        tool_calls = None
        content = f"第{i}步：正在分析收藏夹内容..."

        if call_tool and i == 1:
            tool_calls = [
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": "classify_video",
                        "arguments": json.dumps({"category": "Python教程"}, ensure_ascii=False),
                    },
                }
            ]
            content = None

        if is_last:
            content = final_response

        call_gateway(
            gateway_url=gateway_url,
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
            mock_content=content,
            mock_tool_calls=tool_calls,
            step_label=f"step-{i}/{steps}",
        )


def run_handle_empty_folder(gateway_url: str, run_id: str) -> None:
    task_id = "handle_empty_folder"
    session_id = f"{run_id}-{task_id}"
    print(f"运行任务 {task_id} (run_id={run_id})")

    call_gateway(
        gateway_url=gateway_url,
        session_id=session_id,
        task_id=task_id,
        run_id=run_id,
        mock_content="该收藏夹是空的，没有内容需要处理。",
        mock_tool_calls=None,
        step_label="step-1/1",
    )


SCENARIOS = {
    # 基线：两个任务都正常、合规地完成
    "baseline": {
        "classify_basic": {"steps": 3, "call_tool": True, "final_response": "已完成分类，共整理为2个主题。分类完成。"},
        "handle_empty_folder": True,
    },
    # 回归：classify_basic 步数远超 max_steps=8，触发硬性检查失败
    "regression": {
        "classify_basic": {"steps": 10, "call_tool": True, "final_response": "还在处理中，尚未分类完成。"},
        "handle_empty_folder": True,
    },
    # 部分运行：只跑了 classify_basic，用于测试 compare 对 not_run 的处理
    "partial": {
        "classify_basic": {"steps": 3, "call_tool": True, "final_response": "已完成分类，共整理为2个主题。分类完成。"},
    },
}


def main():
    parser = argparse.ArgumentParser(description="模拟 agent 跑评测任务，产生带 eval 标签的 trace 数据")
    parser.add_argument("--run-id", required=True, help="本次运行的 run_id，比如 v1 / v2")
    parser.add_argument(
        "--scenario",
        required=True,
        choices=list(SCENARIOS.keys()),
        help="选择内置场景：baseline / regression / partial",
    )
    parser.add_argument("--gateway-url", default="http://localhost:8000", help="Phase 1 网关地址")
    args = parser.parse_args()

    scenario = SCENARIOS[args.scenario]
    print(f"=== 开始模拟运行 run_id={args.run_id}, scenario={args.scenario} ===")

    if "classify_basic" in scenario:
        cfg = scenario["classify_basic"]
        run_classify_basic(
            gateway_url=args.gateway_url,
            run_id=args.run_id,
            steps=cfg["steps"],
            call_tool=cfg["call_tool"],
            final_response=cfg["final_response"],
        )

    if scenario.get("handle_empty_folder"):
        run_handle_empty_folder(gateway_url=args.gateway_url, run_id=args.run_id)

    print(f"=== run_id={args.run_id} 模拟完成 ===")


if __name__ == "__main__":
    main()

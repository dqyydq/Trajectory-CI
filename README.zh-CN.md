# Trajectory CI 中文说明

Trajectory CI 是一个给 AI Agent 做回归测试和发版审查的本地工具。

它解决的问题不是“能不能记录 trace”，而是一个更直接的问题：

> 我改了 prompt、模型、工具调用逻辑或系统提示词之后，这个 candidate 版本到底能不能上线？

你把当前版本跑成 **baseline**，把改动后的版本跑成 **candidate**，然后让 Trajectory CI 对比两次运行结果。最终输出一个类似 CI 的发版结论：

```text
REGRESSION GATE: PASSED
```

或者：

```text
REGRESSION GATE: FAILED
- regressed tasks 1 exceeded allowed 0
```

trace、cost、latency、judge reason、dashboard 都不是这个项目的主角。它们是“发版证据”，用来解释为什么这次改动可以发，或者为什么不应该发。

## 一句话理解

Trajectory CI = AI Agent 的回归测试 / 发版审查工具。

它不是 Langfuse、Helicone、Phoenix 那种通用观测平台的替代品。它更聚焦：

- 不是先问“这次调用发生了什么”
- 而是先问“这次 Agent 改动能不能发版”

## 适合什么场景

适合测试这类 Agent 改动：

- 改 prompt 后，回答是否变差
- 换模型后，质量、成本、延迟是否可接受
- 改工具调用逻辑后，是否漏掉关键步骤
- RAG / tool-use / multi-step agent 是否出现行为回归
- 想把 Agent 的人工试用流程变成可重复的 CI 检查

当前版本最适合“任务型 agent 的 baseline vs candidate 对比”。长期运行的 agent 也能测，但通常要先切成 episode，或者用历史 trace 做 replay。

## 快速开始：跑一次发版审查

前提：Docker Desktop 已启动，`.env` 里已经配置好模型供应商 API Key，依赖已安装。

### 1. 启动本地服务

```powershell
.venv\Scripts\activate
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 2. 启动 Dashboard

另开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

Dashboard 地址：

```text
http://127.0.0.1:5173/dashboard/
```

### 3. 跑 baseline

```powershell
.venv\Scripts\activate
python example\deepseek_agent_run.py --task-set agent_release_quality --run-id baseline --profile baseline
```

### 4. 跑 candidate

```powershell
python example\deepseek_agent_run.py --task-set agent_release_quality --run-id candidate --profile candidate
```

### 5. 对比两次运行

```powershell
python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline
```

如果 candidate 发生回归，会看到类似：

```text
REGRESSION GATE: FAILED
- regressed tasks 1 exceeded allowed 0
```

如果通过，则会看到：

```text
REGRESSION GATE: PASSED
```

## Dashboard 应该怎么看

Dashboard 不是普通监控面板。它应该按这个顺序看：

1. **Release decision**：先看能不能发版。
2. **Tasks**：如果失败，看哪个任务回归。
3. **Judge reason**：看为什么 judge 给 candidate 扣分。
4. **Cost / latency impact**：看便宜了、贵了、快了、慢了多少。
5. **Trace evidence**：最后再点 trace，看具体请求、响应和工具调用证据。
6. **Gateway Activity**：这是原始运行证据，不是新手第一入口。

如果一上来就看 cost、latency、raw calls，会觉得项目像一堆指标堆在一起。正确入口永远是：这次改动能不能发。

## 和其他工具有什么区别

| 工具类型 | 主要回答的问题 | 典型输出 |
| --- | --- | --- |
| Langfuse / Helicone / Phoenix | 这次 LLM 调用或 trace 发生了什么？ | traces、logs、scores、dashboards |
| Trajectory CI | 这次 Agent 改动能不能发版？ | baseline-vs-candidate release gate、任务 diff、证据 |

Trajectory CI 不试图在 tracing 能力上打败成熟工具。它把 tracing 当成数据层，用来支撑“发版审查”这个更窄的问题。

## 为什么 cost 有意义

cost 不是为了记账。

它是发版判断的一部分。

例如 candidate 版本可能：

- 成本下降 60%
- 延迟下降 50%
- 但关键任务质量下降

这种情况下，Trajectory CI 应该给出失败结论，因为“便宜但变差”不是一个安全的发版。

## 怎么接入自己的 Agent

你的 Agent 不需要改成某个特定框架。只要它使用 OpenAI-compatible 或 Anthropic-compatible client，就可以通过本地 gateway 采集证据。

OpenAI-compatible 示例：

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-provider-key",
    base_url="http://127.0.0.1:8000/v1",
)

response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "Should we ship this candidate?"}],
    extra_headers={
        "X-Eval-Task-Id": "release_tradeoff",
        "X-Eval-Run-Id": "candidate",
        "X-Session-Id": "agent_release_quality:release_tradeoff:candidate",
    },
)
```

关键是这几个 header：

- `X-Eval-Task-Id`：当前任务 ID
- `X-Eval-Run-Id`：当前运行版本，比如 `baseline` 或 `candidate`
- `X-Session-Id`：一次任务运行的会话 ID，建议包含 task set、task id 和 run id

## Task Set 和 Gate

一个 task set 定义你的 Agent 必须持续做好的任务，以及发版 gate 的规则。

```yaml
gate:
  max_regressed_tasks: 0
  max_failed_tasks: 0
  max_not_run_tasks: 0
  max_cost_increase_pct: 15
  max_latency_increase_pct: 20

tasks:
  - task_id: "agent_release_tradeoff"
    description: "The agent should explain whether a cheaper candidate is safe to ship."
    input: "A cheaper model reduces cost but lowers answer quality. Should we ship it?"
    judge_rubric: "Reward answers that weigh quality, cost, latency, and regression risk."
```

含义是：

- 不允许任务回归
- 不允许 candidate 有失败任务
- 不允许任务没跑
- 成本和延迟涨幅不能超过配置阈值

## 长时间运行的 Agent 能不能测

能，但要把长时间行为切成可审查的 episode。

例如：

- 一次工单处理
- 一段用户会话
- 一次巡检任务
- 一段生产 trace replay
- 一批代表性历史任务

当前版本最适合“固定任务集 + baseline/candidate 对比”。未来可以扩展成：

```text
生产 trace / 历史 episode
        ↓
baseline 行为摘要
        ↓
candidate replay
        ↓
按 episode 比较
        ↓
release gate
```

## 项目模块怎么理解

不要把这些模块看成一堆功能点，它们其实服务同一条主线：

| 模块 | 作用 |
| --- | --- |
| Gateway | 采集 Agent 调用证据 |
| Trace / Span | 保存任务执行过程 |
| Cost / Latency | 作为发版风险指标 |
| Eval Compare | 对比 baseline 和 candidate |
| Judge | 判断质量是否下降 |
| Regression Gate | 输出能不能发版 |
| Dashboard | 展示发版结论和证据 |
| Alerts | 运行时异常提醒，辅助排查 |

主线只有一条：**判断 Agent 改动能不能上线**。

## 常用命令

运行测试：

```powershell
.venv\Scripts\activate
python -m pytest -q
```

前端构建：

```powershell
cd frontend
npm install
npm run build
```

导出 markdown 报告：

```powershell
python -m eval compare --task-set agent_release_quality --run-id candidate --against baseline --export-markdown report.md
```

## 当前定位

Trajectory CI 当前最适合：

- 个人项目展示
- Agent 开发迭代
- Prompt / model / tool 改动的回归测试
- 本地优先的 release review
- 面试中展示“我不是只会做 trace，我能把 observability 变成发版决策”

它的核心不是“我记录了多少数据”，而是：

> 我能告诉你这次 Agent 改动能不能发版，并解释原因。

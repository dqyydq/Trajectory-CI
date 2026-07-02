# Agent 可观测性网关 · Phase 1 构建提示词

> 使用说明：把下面整段内容粘贴给 Claude Code / Cursor / 其他 AI 编程工具作为初始 prompt，
> 或者作为你自己实现时的需求说明书。已根据设计讨论定稿，无需再澄清核心决策。

---

## 角色设定

你是一名资深后端工程师，正在帮我从零搭建一个 **零侵入式 LLM Agent 可观测性网关**（Agent Observability Gateway）。这是一个用于个人简历/学习的工程项目，代码质量要求达到"生产级可读、可维护"的标准，而不是一次性demo脚本。请优先考虑代码的模块边界清晰、职责单一、易于后续扩展（后面会加 Anthropic 协议支持和 trajectory 评测系统）。

## 项目定位

一个本地运行的代理服务：用户只需要把自己 agent 代码里的 LLM API `base_url` 指向这个网关，不需要修改任何业务代码，即可获得完整的调用链路追踪（trace）、token 用量、成本核算，并通过一个简易 dashboard 查看。

核心卖点是"零侵入"——网关在网络协议层拦截，而不是要求用户在代码里手动埋点。

## 技术栈（已定稿，不要更换）

- 语言：Python 3.11+
- Web 框架：FastAPI（利用其原生的 async + streaming response 支持）
- 数据库：PostgreSQL（本地用 Docker 起一个实例即可，请在 README 里给出 docker-compose 启动方式）
- ORM：SQLAlchemy 2.0（async 模式）+ Alembic 做 migration
- HTTP 客户端（用于向真实 OpenAI 转发请求）：httpx（原生支持 async streaming）
- Dashboard：Streamlit，直接读 PostgreSQL 展示数据，不需要额外做 REST API 层给前端用（除非你认为有更好的实现方式，可以提出来跟我讨论）
- 配置管理：Pydantic Settings，成本价目表用一个独立的 YAML 文件承载

## 核心功能范围（Phase 1，只做以下内容，不要提前实现评测系统等 Phase 2 功能）

### 1. OpenAI 协议代理转发

- 完整代理 `POST /v1/chat/completions` 接口，透明转发到真实的 `https://api.openai.com/v1/chat/completions`（真实 API Key 从请求的 Authorization header 里取，网关本身不存储用户的 API Key）
- 同时支持流式（`stream: true`，SSE 响应）和非流式两种模式，客户端行为应该和直接调用 OpenAI 完全一致（除了多了 tracing 副作用）
- 错误透传：如果上游 OpenAI 返回错误，原样透传给客户端，同时也要记录这次失败的调用

### 2. Trace / Span 数据模型（参考 OpenTelemetry 语义）

设计并实现以下核心表（用 SQLAlchemy models 定义，需要用 Alembic 生成 migration）：

- **traces 表**：代表一次完整的任务/会话
  - `trace_id`（主键，UUID）
  - `session_id`（可选，调用方可以通过自定义 header 比如 `X-Session-Id` 传入，用于把多次调用关联到同一个上层任务；如果没传则每次调用是独立的 trace）
  - `started_at`, `ended_at`
  - `metadata`（JSONB，预留字段，Phase 2 评测系统会用）

- **spans 表**：代表一次具体的 LLM 调用（未来也可以扩展成工具调用等其他类型的 span）
  - `span_id`（主键，UUID）
  - `trace_id`（外键关联 traces）
  - `parent_span_id`（可为空，指向同一 trace 内的父 span，用于表达嵌套调用关系）
  - `span_type`（枚举，Phase 1 只有 `llm_call` 一种，为未来扩展预留）
  - `model`（模型名，如 gpt-4o）
  - `request_body`（JSONB，记录请求内容，注意脱敏或至少提供开关）
  - `response_body`（JSONB，记录响应内容；流式请求要把所有 chunk 拼接还原成完整响应后再存）
  - `prompt_tokens`, `completion_tokens`, `total_tokens`
  - `cost_usd`（根据价目表配置计算得出，查不到价格时记 null 并打 warning 日志，不要报错阻断请求）
  - `latency_ms`
  - `status`（success / error）
  - `error_message`（可为空）
  - `is_stream`（bool）
  - `started_at`, `ended_at`

请思考一下索引设计（至少 trace_id、session_id 应该建索引，因为后续查询会频繁按这两个字段过滤）。

### 3. Streaming 处理

这是本项目技术难度最高的部分，请认真实现：

- 用 httpx 的 async streaming 能力，一边从 OpenAI 收流一边转发给客户端（不能等全部收完再转发，否则失去 streaming 的意义）
- 同时在网关内部把所有 SSE chunk 缓存下来，流结束后拼接还原出完整的 response 内容，提取最后一个 chunk 里的 usage 信息（OpenAI 的 streaming 模式下，只有指定 `stream_options: {"include_usage": true}` 时最后一个 chunk 才会带 usage 字段；如果客户端没传这个参数，需要你自己想办法处理——可以选择自动给转发的请求加上这个参数，或者退化为估算 token 数，请把你的方案和权衡跟我说明一下）
- 流式和非流式两种情况，最终都要落到同一套 trace 记录逻辑里（不要写两套重复代码），建议抽象出一个统一的 `record_span(...)` 函数或类，在两个 handler 分支的最后都调用它

### 4. 成本计算

- 从一个 YAML 配置文件读取价目表，格式类似：
```yaml
models:
  gpt-4o:
    input_per_million: 2.50
    output_per_million: 10.00
  gpt-4o-mini:
    input_per_million: 0.15
    output_per_million: 0.60
  # 用户可以自己加自定义/本地模型条目，本地模型可以填 0
```
- 配置文件路径通过环境变量指定，提供一个默认的示例文件
- 找不到对应模型价格时不要抛异常，记录 null 并打 warning

### 5. Dashboard（Streamlit）

至少包含以下三个视图：

- **调用列表**：分页展示所有 span，可按 trace_id/session_id/model/status 筛选，展示耗时、token、成本
- **Trace 详情/树状展开**：点进某个 trace，能看到它下面所有 span 按 parent_span_id 组织的树状结构（哪怕 Phase 1 阶段大部分 trace 可能只有一层，也要把展示逻辑写成支持任意深度的递归展示，为后续真正出现嵌套调用时做好准备）
- **成本趋势图**：按时间聚合展示成本/调用量趋势（用 Streamlit 自带的图表组件即可，不需要额外引入前端图表库）

## 项目结构建议

请先给我一份你计划的目录结构（不用太细，到模块级别即可），确认后再开始写代码。大致方向是把"代理转发逻辑"、"trace 记录逻辑"、"成本计算逻辑"、"数据库模型"、"dashboard" 分成清晰的模块/包，方便后续独立扩展和测试。

## 实现要求

1. **先设计，后编码**：先给出目录结构和核心数据模型设计，等我确认之后再开始写具体实现代码，不要一次性生成整个项目。
2. **分步交付**：建议按这个顺序实现并逐步验证：① 数据库模型 + migration → ② 非流式代理转发 + trace 记录打通 → ③ 流式代理转发 + trace 记录复用 → ④ 成本计算模块 → ⑤ Streamlit dashboard。每一步做完给我一个可以本地验证的方式（比如一条 curl 命令或测试脚本）。
3. **测试**：核心的 trace 记录逻辑、成本计算逻辑需要写单元测试（用 pytest），代理转发部分至少写一个集成测试（可以 mock 上游 OpenAI 响应）。
4. **README**：项目最后要有一份清晰的 README，包含：项目背景一句话说明、架构图（文字描述即可）、本地启动步骤（含 PostgreSQL docker-compose）、使用示例（怎么把某个 agent 的 base_url 指过来）。
5. **不要过度设计**：这是 Phase 1，不要提前实现 Anthropic 协议支持、trajectory 评测系统、鉴权/多租户等 Phase 2+ 的内容，除非是为了不返工而做的合理预留（比如 span_type 枚举预留扩展空间是合理的，但不要真的去实现工具调用的追踪逻辑）。

## 现在请你做的第一件事

请先输出你计划的项目目录结构和核心数据模型的 SQLAlchemy 代码草稿，不要直接开始写业务逻辑代码。我确认没问题之后，我们再按上面的分步顺序继续。

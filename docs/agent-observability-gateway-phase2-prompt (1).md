# Agent 可观测性网关 · Phase 2 构建提示词（Trajectory 评测系统）

> 使用说明：把下面整段内容粘贴给 Claude Code / Cursor / 其他 AI 编程工具作为初始 prompt。
> 这是 Phase 1（零侵入可观测网关）的延续，Phase 1 已完成并跑通。已根据设计讨论定稿，
> 核心决策不需要再澄清。

---

## 角色设定

你是一名资深后端工程师，正在帮我给已有的 **Agent 可观测性网关** 项目扩展 Phase 2 功能：一套基于已采集 trace 数据的 **Trajectory 回归测试系统**。请先阅读现有代码库（Phase 1 的 `app/db/models.py`、`app/tracing/`、`app/cost/` 等模块），理解现有架构后再开始设计，Phase 2 的实现要尽量复用已有的数据模型和模块划分风格，不要另起炉灶。

## 项目定位

Phase 2 不引入新的数据采集环节，而是**直接复用 Phase 1 网关已经记录的 trace/span 数据**。核心能力是：给同一批"测试任务"跑不同版本的 agent（打不同的 `run_id` 标签），事后对两次运行做自动化对比，判断"这次改动是让 agent 变好了还是变差了"，类似给 agent 系统做 CI 回归测试。

## 数据模型变更（在 Phase 1 基础上扩展，不是重新设计）

在现有 `Trace` 表上新增两个可空字段：

```python
# app/db/models.py 的 Trace 类新增
eval_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
eval_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
```

这两个字段通过调用方在请求里携带的自定义 header 写入（`X-Eval-Task-Id`、`X-Eval-Run-Id`），复用 Phase 1 已有的 trace 创建/更新逻辑，只需要在 `tracing/recorder.py` 里增加对这两个 header 的读取和落库，不需要改动整体记录流程。

新增一个复合索引方便评测查询按 `(eval_task_id, eval_run_id)` 拉数据：

```python
Index("ix_traces_eval_task_run", Trace.eval_task_id, Trace.eval_run_id)
```

生成对应的 Alembic migration。

## 任务集定义文件（YAML DSL）

新增 `eval/task_sets/` 目录存放任务集文件，格式如下（这是本次设计的核心 schema，请严格按此实现）：

```yaml
# eval/task_sets/bilibili_agent_v1.yaml
tasks:
  - task_id: "classify_basic"
    description: "整理一个包含10个视频的收藏夹，按主题分类"
    input: |
      请帮我整理这个收藏夹：[视频列表...]
    # 评分要点可选，不写则 judge 走通用质量准则
    judge_rubric: |
      好的回答应该：
      1. 正确识别出至少3个不同主题分类
      2. 没有遗漏收藏夹里提到的任何一个视频
      3. 分类理由清晰、语气得体
    checks:
      - type: tool_called
        tool_name: classify_video
      - type: max_steps
        value: 8
      - type: response_contains
        keyword: "分类完成"
      - type: custom
        function: "eval.custom_checks.no_duplicate_categories"

  - task_id: "handle_empty_folder"
    description: "处理一个空收藏夹，验证边界情况"
    input: "请帮我整理这个收藏夹：[]"
    # 没有 judge_rubric，走通用打分
    checks:
      - type: response_contains
        keyword: "没有内容"
```

请用 Pydantic 定义这个 YAML 的 schema（`eval/schemas.py`），加载时做校验，格式错误要有清晰的报错信息（指出是哪个 task_id 的哪个字段有问题）。

## 核心模块设计

在现有项目结构基础上新增 `eval/` 顶层包，建议结构：

```text
eval/
  __init__.py
  cli.py                    # CLI 入口（python -m eval ...）
  schemas.py                 # 任务集 YAML 的 Pydantic schema
  task_sets/
    bilibili_agent_v1.yaml
  loader.py                  # 加载并校验任务集文件
  data_fetcher.py             # 从 Phase 1 数据库按 (task_id, run_id) 拉取对应 trace/span
  checks/
    __init__.py
    registry.py               # 声明式 check type 到处理函数的映射
    builtin.py                 # tool_called / max_steps / response_contains 等内置检查
  custom_checks.py            # 用户自定义的 custom 类型检查函数存放处
  judge/
    __init__.py
    prompts.py                 # LLM-as-judge 的 prompt 模板（有rubric / 无rubric 两套）
    scorer.py                   # 调用 judge 模型打分，注意这里的 LLM 调用要把
                                 # base_url 指向 Phase 1 网关本身，并在请求 header
                                 # 里带上一个标识（比如 X-Span-Type: llm_judge），
                                 # 让 Phase 1 记录时能识别这是 judge 调用而不是普通业务调用
  compare/
    __init__.py
    runner.py                   # 核心编排逻辑：读任务集 -> 拉数据 -> 跑checks -> 跑judge -> 生成对比结果
    diff.py                     # 逐任务 diff 计算逻辑
    report.py                   # 生成汇总报告（存库 + 可选导出markdown）
  db/
    models.py                   # EvalReport / EvalTaskResult 等评测结果的持久化模型
```

## 评分/对比核心流程（`compare/runner.py` 的编排逻辑）

对每个 `task_id`，分别处理 `run_id=v1` 和 `run_id=v2` 两次运行：

1. 从数据库按 `(eval_task_id, eval_run_id)` 拉取对应的 trace 及其下所有 span
2. 依次执行任务定义里的 `checks` 列表：
   - 任何一条 check 未通过，整体判定为 `hard_check_failed`，**不再调用 LLM judge**（省钱），记录是哪条 check 失败、失败原因
   - 全部通过，进入下一步
3. 调用 LLM judge 打分：
   - 有 `judge_rubric` 走精确评分 prompt，没有走通用评分 prompt（两套 prompt 模板在 `judge/prompts.py` 分别维护）
   - 记录分数（比如1-5分）和打分理由文本
4. 把每个 task 在两个 run 下的结果（硬性检查结果 + judge 分数）配对，计算 diff：
   - 明确标出"从pass变fail"、"分数下降超过某个阈值"这类退步情况
5. 汇总生成整体报告：整体通过率对比、平均分对比、逐任务 diff 列表

## 结果持久化

新增两张表（不要复用 Phase 1 的 Trace/Span 表存这些，评测结果和调用trace是不同性质的数据）：

- `eval_reports`：一次 compare 命令执行的整体记录（`report_id`, `task_set_name`, `run_id_a`, `run_id_b`, `created_at`, 整体汇总统计的 JSONB 字段）
- `eval_task_results`：每个 task 在这次对比里的明细（`report_id` 外键, `task_id`, `run_a_check_passed`, `run_a_judge_score`, `run_b_check_passed`, `run_b_judge_score`, `regressed`布尔字段, `detail` JSONB存具体diff内容）

## CLI 设计

```bash
python -m eval compare --task-set bilibili_agent_v1 --run-id v2 --against v1
```

执行完成后：
- 结果写入上面两张表
- 终端打印一份简洁的文本汇总（整体通过率、平均分、哪些task退步了）
- 支持 `--export-markdown report.md` 参数，把详细报告导出成一份 markdown 文件

## Dashboard 扩展

在现有 Streamlit dashboard 基础上新增一个页面（不要重写整个 dashboard，新增一个 tab/page）：

- 顶部：选择一份历史 `eval_report`，展示整体通过率/平均分对比（v1 vs v2）
- 下方：逐任务 diff 表格，退步的行要高亮标红
- 点击某一行任务，展开显示这个任务在两次 run 下的完整 trajectory（复用 Phase 1 已有的 trace 树状展开组件，不要重新实现一套）

## 实现要求

1. **先设计后编码**：先给出 `eval/` 目录结构确认、Pydantic schema 定义、以及 `eval_reports`/`eval_task_results` 两张表的字段设计，等我确认后再写实现代码。
2. **分步交付顺序建议**：① 数据模型变更（Trace新增字段 + 两张评测结果表 + migration）→ ② 任务集YAML加载与校验 → ③ 内置 checks 实现（先不做judge）→ ④ judge 打分模块（记得接入 Phase 1 网关）→ ⑤ compare 编排逻辑 + diff计算 → ⑥ CLI → ⑦ dashboard 页面。每一步给出可本地验证的方式。
3. **测试**：checks 的每种内置类型要有单元测试；diff 计算逻辑要有单元测试（构造几种典型的"变好/变差/不变"场景断言结果正确）；建议写一个端到端集成测试，用一份mini任务集+mock的两次trace数据，跑通完整 compare 流程。
4. **复用优先**：任何 Phase 1 已经实现的能力（数据库连接、trace查询、dashboard的树状展示组件）都要复用，不要重复造轮子；只有 Phase 2 独有的逻辑才新建代码。
5. **README 更新**：在现有 README 基础上新增一节说明 Phase 2 的使用方式（怎么写任务集文件、怎么跑两次agent产生对比数据、怎么执行compare命令）。

## 现在请你做的第一件事

先阅读现有 Phase 1 代码库的目录结构和 `app/db/models.py`、`app/tracing/recorder.py`，简要总结你的理解，然后输出你计划的 `eval/` 目录结构、Pydantic schema 草稿、以及两张新表的 SQLAlchemy 模型草稿。确认没问题后我们再按上面的分步顺序继续。

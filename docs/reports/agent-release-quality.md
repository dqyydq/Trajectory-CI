# Eval Report: agent_release_quality

Compared `candidate-20260704103959` against `baseline-20260704103959`.

## Regression Gate: FAILED

- regressed tasks 1 exceeded allowed 0

## Summary

- Run A pass rate: 100.00%
- Run B pass rate: 100.00%
- Run A average score: 5.0
- Run B average score: 4.6667
- Regressed tasks: 1
- Candidate failed tasks: 0
- Candidate not-run tasks: 0
- Cost: `baseline-20260704103959` $0.000579 -> `candidate-20260704103959` $0.000188 (-67.5302%)
- Avg latency: `baseline-20260704103959` 10445.33ms -> `candidate-20260704103959` 3646.33ms (-65.0913%)

## Task Diff

### observability_release_value

- Status: `judged` -> `judged`
- Regressed: `False`
- Reason: no regression detected
- Score A: 5.0
- Score B: 5.0
- Judge reason A: The response thoroughly connects observability to release decisions (automated gates, rollback decisions), regression diagnosis (pre/post distributions of tool calls, safety regressions), task trajectory evidence (actual tool calls, LLM reasoning chain, latency per step), cost/latency risk (cost explosion, runaway loops, per-request token usage), and failure debugging (full chain leading to errors, hallucinated tool names). It provides a concrete example and explicitly distinguishes observability from generic logging, meeting all high-scoring criteria.
- Judge reason B: The response clearly connects observability to release decisions (releasing blind without it), cost/latency risks (unbounded token usage, slow tool calls), failure debugging (hallucinations, unexpected decisions), and task trajectory evidence (traces for agent decisions). It addresses non-determinism specific to LLM agents, avoiding generic logging statements.
- Trace A: 6ca2cde4-5119-4ee0-943b-e970f6acd6c7
- Trace B: 1fa5200a-8fb6-4448-9e9d-e5657b41ef57

### cost_quality_tradeoff

- Status: `judged` -> `judged`
- Regressed: `False`
- Reason: no regression detected
- Score A: 5.0
- Score B: 5.0
- Judge reason A: The recommendation explicitly weighs quality, cost, latency, and regression risk, prioritizes correctness over cost, and recommends further evaluation (audit, controlled rollout) rather than shipping solely for cost savings. It fully aligns with the rubric's criteria for a high score.
- Judge reason B: The recommendation explicitly weighs quality against cost, rejecting the cheaper option due to misleading outputs. It identifies regression risk (omitting caveats) and recommends fixing the prompt and re-testing, which constitutes a gate/further evaluation. Latency is not directly mentioned, but the reasoning sufficiently covers the core trade-offs and avoids optimizing solely for cost or brevity.
- Trace A: 9723f51d-5955-4fec-8389-33c4250fbe72
- Trace B: 0a69f179-5527-41c0-9577-8c0eaf38a54f

### failed_agent_investigation

- Status: `judged` -> `judged`
- Regressed: `True`
- Reason: judge score decreased by 1.00
- Score A: 5.0
- Score B: 4.0
- Judge reason A: The response provides a concrete, step-by-step debugging approach that prioritizes inspecting trace steps, tool calls, and model outputs, with clear evidence categories (tool API changes, model drift, environmental mismatches, input shifts). It gives actionable fixes for each root cause and avoids vague advice, fully aligning with the rubric's emphasis on hard-check failure reasons, errors, and latency (via timeouts). While token/cost anomalies are not explicitly listed, the overall specificity and practicality justify the highest score.
- Judge reason B: The response correctly identifies inspecting the tool's response and recent environment changes, which are concrete evidence. It provides a clear guide for fixing the issue. However, it omits other important evidence like trace steps, model outputs, latency, and token cost anomalies, which would make the debugging more comprehensive.
- Trace A: 7b6e29ce-cf13-4a76-8376-b07dece0885f
- Trace B: 85729623-9dfd-4a0a-924c-8e0a1125a471

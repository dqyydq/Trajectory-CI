# Example Release-Review Flows

These examples show how to use Trajectory CI as an agent release review tool: capture a baseline, capture a candidate, compare them, and inspect the release verdict.

## Real DeepSeek Release Review

This is the main product story and the best first demo. It uses real DeepSeek calls through the local gateway and the `agent_release_quality` task set.

Prerequisites:

1. PostgreSQL is running and migrations are applied.
2. The gateway is running on `http://127.0.0.1:8000`.
3. Project `.env` contains:

```env
DEEPSEEK_API_KEY=your_real_key
OPENAI_BASE_URL=https://api.deepseek.com
PRICING_CONFIG_PATH=config/pricing.example.yaml
```

Run the baseline:

```powershell
.venv\Scripts\activate
python example\deepseek_agent_run.py --task-set agent_release_quality --run-id baseline-YYYYMMDDHHMMSS --profile baseline
```

Run the candidate:

```powershell
python example\deepseek_agent_run.py --task-set agent_release_quality --run-id candidate-YYYYMMDDHHMMSS --profile candidate
```

Compare the two runs:

```powershell
python -m eval compare --task-set agent_release_quality --run-id candidate-YYYYMMDDHHMMSS --against baseline-YYYYMMDDHHMMSS --export-markdown docs\reports\agent-release-quality.md --no-fail-on-gate
```

Expected result: the command prints `REGRESSION GATE: PASSED` or `REGRESSION GATE: FAILED`, and the dashboard shows the same release decision first. The checked-in report demonstrates a realistic tradeoff: the candidate is cheaper and faster, but the release gate fails because judge scoring detects a quality regression.

## Minimal DeepSeek Smoke Flow

Use this when you only want to verify real provider connectivity and eval tagging.

```powershell
.venv\Scripts\activate
python example\deepseek_agent_run.py --run-id v1
python example\deepseek_agent_run.py --run-id v2
python -m eval compare --task-set deepseek_smoke --run-id v2 --against v1 --skip-judge
```

Expected result: Trajectory CI creates two runs and a comparison report without judge calls. Use the dashboard to confirm that the traces are linked to eval task IDs and run IDs.

## Local Mock Flow

Use this when you want a no-cost local validation. The mock server emulates an OpenAI-compatible upstream.

Terminal 1:

```powershell
.venv\Scripts\activate
python example\mock_upstream_server.py
```

Terminal 2, start the gateway pointed at the mock upstream:

```powershell
.venv\Scripts\activate
$env:OPENAI_BASE_URL="http://127.0.0.1:9000/v1"
uvicorn app.main:app --reload --port 8000
```

Terminal 3, generate mock eval traces:

```powershell
.venv\Scripts\activate
python example\simulate_agent_run.py --run-id v1 --scenario baseline --gateway-url http://127.0.0.1:8000
python example\simulate_agent_run.py --run-id v2 --scenario regression --gateway-url http://127.0.0.1:8000
python example\simulate_agent_run.py --run-id v3 --scenario partial --gateway-url http://127.0.0.1:8000
```

Then compare:

```powershell
python -m eval compare --task-set bilibili_agent_v1 --run-id v2 --against v1 --skip-judge
python -m eval compare --task-set bilibili_agent_v1 --run-id v3 --against v1 --skip-judge
```

Expected result: `v2` shows a regression-style comparison, and `v3` demonstrates not-run task handling. After mock testing, restart the gateway with the real `.env` so provider calls go to DeepSeek again.

## Anthropic Tool-Use Flow

Use this when you want to verify the Anthropic Messages adapter through the same release-evidence gateway.

```powershell
.venv\Scripts\activate
python example\anthropic_tool_agent_run.py "List the top-level files, then read README.md if it exists."
```

Expected result: the agent call is proxied through `http://127.0.0.1:8000/v1/messages`, and spans are tagged with session and tenant headers so they appear as trace evidence in the dashboard.

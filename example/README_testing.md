# Example Flows

This directory contains runnable examples for validating the Agent Observability Gateway.

## Real DeepSeek API flow

Use this when you want to call your real DeepSeek API through the local gateway and generate Phase 2 eval data.

Prerequisites:

1. PostgreSQL is running and migrations are applied.
2. The gateway is running on `http://127.0.0.1:8000`.
3. Project `.env` contains:

```env
DEEPSEEK_API_KEY=your_real_key
OPENAI_BASE_URL=https://api.deepseek.com
PRICING_CONFIG_PATH=config/pricing.example.yaml
```

Run two eval runs:

```powershell
.venv\Scripts\activate
python example\deepseek_agent_run.py --run-id v1
python example\deepseek_agent_run.py --run-id v2
```

Compare them without judge calls:

```powershell
python -m eval compare --task-set deepseek_smoke --run-id v2 --against v1 --skip-judge
```

Compare them with judge calls through the gateway:

```powershell
python -m eval compare --task-set deepseek_smoke --run-id v2 --against v1
```

The real API example uses:

- `base_url=http://127.0.0.1:8000/v1`
- `httpx.Client(trust_env=False)` to avoid local proxy settings breaking localhost calls
- `X-Eval-Task-Id`, `X-Eval-Run-Id`, and `X-Session-Id` headers

The matching task set is `eval/task_sets/deepseek_smoke.yaml`.


## Agent release quality case

This is the real Trajectory CI case study used in the README. It compares a complete baseline prompt against a shorter candidate prompt using real DeepSeek calls through the gateway.

```powershell
.venv\Scripts\activate
python example\deepseek_agent_run.py --task-set agent_release_quality --run-id baseline-YYYYMMDDHHMMSS --profile baseline
python example\deepseek_agent_run.py --task-set agent_release_quality --run-id candidate-YYYYMMDDHHMMSS --profile candidate
python -m eval compare --task-set agent_release_quality --run-id candidate-YYYYMMDDHHMMSS --against baseline-YYYYMMDDHHMMSS --export-markdown docs\reports\agent-release-quality.md --no-fail-on-gate
```

The checked-in report shows a realistic tradeoff: the candidate is cheaper and faster, but the release gate fails because judge scoring detects a quality regression.

## Mock upstream flow

Use this when you want a no-cost local-only test. The mock server emulates an OpenAI-compatible upstream.

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

After mock testing, restart the gateway with the real `.env` so production-like calls go to DeepSeek again.
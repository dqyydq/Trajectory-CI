from __future__ import annotations

import argparse
import glob
import os
import subprocess
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from anthropic import Anthropic
except ImportError as exc:  # pragma: no cover - user-facing script guard
    raise SystemExit(
        "Missing dependency: anthropic. Install with `uv pip install anthropic python-dotenv` "
        "after activating .venv."
    ) from exc


WORKDIR = Path.cwd().resolve()
DEFAULT_MODEL = "claude-3-5-haiku-latest"

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command in the current workspace.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a text file from the current workspace.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write text content to a file in the current workspace.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text once in a file in the current workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "glob",
        "description": "Find workspace files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
]


def load_project_env() -> None:
    root = Path(__file__).resolve().parents[1]
    fallback_env = Path(r"D:\python_code\learn-claude-code-main\.env")
    if fallback_env.exists():
        load_dotenv(fallback_env, override=False)
    load_dotenv(root / ".env", override=True)


def default_gateway_api_key() -> str:
    explicit = os.getenv("GATEWAY_API_KEY", "").strip()
    if explicit:
        return explicit
    configured = os.getenv("GATEWAY_API_KEYS", "")
    return next((key.strip() for key in configured.split(",") if key.strip()), "")

def safe_path(path: str) -> Path:
    resolved = (WORKDIR / path).resolve()
    if not resolved.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {path}")
    return resolved


def run_bash(command: str) -> str:
    blocked = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/", "format "]
    if any(item in command.lower() for item in blocked):
        return "Error: dangerous command blocked"
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 120 seconds"
    except OSError as exc:
        return f"Error: {exc}"


def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        if limit is not None and limit >= 0 and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as exc:
        return f"Error: {exc}"


def run_write(path: str, content: str) -> str:
    try:
        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        target = safe_path(path)
        text = target.read_text(encoding="utf-8", errors="replace")
        if old_text not in text:
            return f"Error: text not found in {path}"
        target.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_glob(pattern: str) -> str:
    try:
        matches = []
        for match in glob.glob(pattern, root_dir=WORKDIR, recursive=True):
            resolved = (WORKDIR / match).resolve()
            if resolved.is_relative_to(WORKDIR):
                matches.append(match.replace("\\", "/"))
        return "\n".join(sorted(matches)) if matches else "(no matches)"
    except Exception as exc:
        return f"Error: {exc}"


TOOL_HANDLERS = {
    "bash": run_bash,
    "read_file": run_read,
    "write_file": run_write,
    "edit_file": run_edit,
    "glob": run_glob,
}


def tool_result_for(block: Any) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(block.name)
    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
    print(f"> {block.name}: {str(output)[:240]}")
    return {"type": "tool_result", "tool_use_id": block.id, "content": output}


def agent_loop(
    *,
    client: Anthropic,
    model: str,
    query: str,
    extra_headers: dict[str, str],
    max_tokens: int,
) -> str:
    system = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."
    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    while True:
        response = client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=TOOLS,
            max_tokens=max_tokens,
            extra_headers=extra_headers,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")

        results = [tool_result_for(block) for block in response.content if getattr(block, "type", None) == "tool_use"]
        messages.append({"role": "user", "content": results})


def main() -> None:
    load_project_env()
    parser = argparse.ArgumentParser(description="Run an Anthropic tool-use agent through the local gateway.")
    parser.add_argument("prompt", nargs="?", default="List the top-level files in this workspace, then read README.md if it exists.")
    parser.add_argument("--gateway-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default=os.getenv("MODEL_ID", DEFAULT_MODEL))
    parser.add_argument("--session-id", default="anthropic-tool-agent-demo")
    parser.add_argument("--tenant-id", default=os.getenv("DEFAULT_TENANT_ID", "default"))
    parser.add_argument("--gateway-api-key", default=default_gateway_api_key())
    parser.add_argument("--api-key-env", default="ANTHROPIC_API_KEY")
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args()

    api_key = os.getenv(args.api_key_env) or os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is not set in .env. Add your upstream provider API key first.")

    headers = {
        "X-Session-Id": args.session_id,
        "X-Tenant-Id": args.tenant_id,
        "X-Span-Type": "agent_step",
    }
    if args.gateway_api_key:
        headers["X-Gateway-Api-Key"] = args.gateway_api_key

    client = Anthropic(api_key=api_key, base_url=args.gateway_base_url)
    answer = agent_loop(
        client=client,
        model=args.model,
        query=args.prompt,
        extra_headers=headers,
        max_tokens=args.max_tokens,
    )
    print("\nFinal answer:")
    print(answer.strip() or "(no text response)")
    print("\nDashboard:")
    print("http://127.0.0.1:5173/dashboard/")


if __name__ == "__main__":
    main()

"""GitHub Actions runner for J."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.action import extract_action, strip_identity_preamble, truncate_tool_output
from app.agent import ToolRegistry
from github_agent.llm_github import chat as github_chat


def load_event() -> dict[str, Any]:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("GITHUB_EVENT_PATH is not set")
    with open(event_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_comment_command(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("/j"):
            return stripped[2:].strip()
    return body.strip()


def build_system_prompt(repo_full_name: str, tool_registry: ToolRegistry) -> str:
    return (
        f"You are J, the Sovereign Shards agent for the repository {repo_full_name}. "
        "When you need to inspect repository contents or run tooling, issue exactly one "
        "ACTION payload in the form ACTION:{\"tool\": \"...\", \"args\": [...]} and wait for the tool result. "
        "Do not invent file contents. Only use tools when necessary. "
        "If you can answer without tools, provide a concise final response.\n\n"
        f"{tool_registry.describe()}"
    )


def build_issue_prompt(command: str, event: dict[str, Any]) -> str:
    issue = event.get("issue", {})
    title = issue.get("title", "")
    body = issue.get("body", "")
    return (
        f"A user requested: {command}\n\n"
        f"Issue title: {title}\n"
        f"Issue body:\n{body}\n\n"
        "Respond as J and follow the request."
    )


def build_pull_request_prompt(event: dict[str, Any]) -> str:
    pr = event.get("pull_request", {})
    title = pr.get("title", "")
    body = pr.get("body", "")
    head = pr.get("head", {}).get("ref", "")
    base = pr.get("base", {}).get("ref", "")
    return (
        "Auto-review the pull request changes and provide a clear summary, issues, and suggested improvements.\n\n"
        f"Title: {title}\n"
        f"Branch: {head} -> {base}\n"
        f"Description:\n{body}\n"
    )


def run_agent_loop(messages: list[dict[str, str]], registry: ToolRegistry, model: str, budget: int) -> str:
    final_response = ""
    for step in range(budget):
        reply = github_chat(model, messages)
        cleaned = strip_identity_preamble(reply)
        action = extract_action(cleaned)
        if not action:
            final_response = cleaned
            break

        tool_name = action.get("tool")
        tool_args = action.get("args", [])
        if not isinstance(tool_args, list):
            tool_args = [tool_args]

        tool_result = registry.execute(tool_name, tool_args)
        tool_result = truncate_tool_output(tool_result)

        messages.append({"role": "assistant", "content": cleaned})
        messages.append({"role": "user", "content": f"TOOL RESULT:\n{tool_result}"})
        final_response = cleaned
    else:
        final_response = (
            "[J NOTICE] Maximum tool budget reached. "
            "Providing the latest response.\n\n" + final_response
        )
    return final_response


def write_response(response: str) -> None:
    header = "🔮 **J** · _Sovereign Shards Agent_\n\n"
    output = header + response.strip() + "\n"
    Path(ROOT / "j_response.md").write_text(output, encoding="utf-8")
    print(output)


def main() -> int:
    event = load_event()
    repo = event.get("repository", {}).get("full_name", "unknown/repo")
    registry = ToolRegistry(ROOT)
    system_prompt = build_system_prompt(repo, registry)

    messages = [{"role": "system", "content": system_prompt}]
    model = os.getenv("J_MODEL", "gpt-4o-mini")
    budget = int(os.getenv("J_TOOL_BUDGET", "3"))

    if event.get("issue") and event.get("comment"):
        command = parse_comment_command(str(event.get("comment", {}).get("body", "")))
        if not command:
            response = "[J ERROR] No /j command found in the comment."
            write_response(response)
            return 0
        messages.append({"role": "user", "content": build_issue_prompt(command, event)})
    elif event.get("pull_request"):
        messages.append({"role": "user", "content": build_pull_request_prompt(event)})
    else:
        response = "[J ERROR] Unsupported GitHub event."
        write_response(response)
        return 0

    response = run_agent_loop(messages, registry, model, budget)
    write_response(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Executor: walk AgentSteps one at a time, calling tools via the registry.

The executor sends each step to the LLM as a focused sub-prompt,
collects tool calls, runs them through the ToolRegistry, and records results.
Respects autonomy mode: in 'semi', side-effects require confirmation.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from app.agent.contracts import AgentStep, AgentTask, ToolCall, ToolResult

if TYPE_CHECKING:
    from app.agent.tool_registry import ToolRegistry

PROCESS_PAUSE_SECONDS = 0.2
MAX_ACTION_RETRIES = 1
ACTION_RETRY_PROMPT = "You must call a tool. Respond ONLY with ACTION:{\"tool\":...,\"args\":[...]}"
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ACCUMULATOR_PATH = BASE_DIR / "memory" / "task_accumulator.md"


def build_step_prompt(step: AgentStep, tool_listing: str, tool_budget: int = 0) -> str:
    """Build a focused prompt for one step."""
    prompt = (
        f"[CURRENT STEP] {step.id}: {step.goal}\n"
        f"[SUCCESS CRITERIA] {step.success_criteria}\n\n"
        f"Available tools:\n{tool_listing}\n\n"
        "For multi-file tasks, write partial results to disk after every 2-3 reads using write_file. Do not rely on holding all data in context.\n\n"
        "If you need a tool, respond with:\n"
        "ACTION:\n"
        '{"tool": "<name>", "args": [...]}\n\n'
        "Otherwise, respond with your result directly."
    )
    if tool_budget > 10:
        prompt += "\nIMPORTANT: Write intermediate results to a scratch file. Context may be compressed between steps."
    return prompt


def needs_confirmation(tool_name: str, registry: "ToolRegistry", mode: str) -> bool:
    """Return True if this tool call requires user confirmation."""
    if mode in ("auto-safe", "auto-full"):
        if mode == "auto-safe" and registry.get_side_effect(tool_name) == "exec":
            return True  # auto-safe blocks shell exec
        return False
    if mode == "semi":
        effect = registry.get_side_effect(tool_name)
        return effect in ("write", "exec")
    return True  # manual mode: always confirm



def validate_action_payload(action: dict, registry: "ToolRegistry") -> Optional[str]:
    """Validate extracted ACTION payload; return error text, or None if valid."""
    tool_name = action.get("tool")
    args = action.get("args", [])

    if not tool_name or not isinstance(tool_name, str):
        return "Invalid ACTION: missing 'tool'."
    if not isinstance(args, list):
        return "Invalid ACTION: args must be a list."
    if registry.get(tool_name) is None:
        return f"Unknown tool '{tool_name}'."
    return None

def execute_tool_call(
    call: ToolCall,
    registry: "ToolRegistry",
    step_goal: str = "",
    tool_budget: int = 0,
) -> ToolResult:
    """Execute a single validated tool call and return the result."""
    time.sleep(PROCESS_PAUSE_SECONDS)
    output = registry.execute(call.name, list(call.args.values()) if isinstance(call.args, dict) else list(call.args))
    _maybe_append_accumulator(call.name, output, step_goal=step_goal, tool_budget=tool_budget)

    ok = not output.startswith("[TOOL ERROR]")
    error = output if not ok else ""
    return ToolResult(
        name=call.name,
        ok=ok,
        output=output if ok else "",
        error=error,
    )


def _maybe_append_accumulator(tool_name: str, output: str, step_goal: str, tool_budget: int) -> None:
    goal = step_goal.lower()
    if tool_budget <= 5:
        return
    if not any(k in goal for k in ("read", "extract", "gather")):
        return
    if tool_name not in ("run_read", "read_file", "run_search"):
        return
    ACCUMULATOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ACCUMULATOR_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\n## {tool_name} @ {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(output[:4000] + "\n")


def format_tool_result(result: ToolResult) -> str:
    """Format a ToolResult for injection back into the conversation."""
    status = "OK" if result.ok else "ERROR"
    content = result.output if result.ok else result.error
    return (
        f"[TOOL {status}] {result.name}\n"
        f"{content}"
    )

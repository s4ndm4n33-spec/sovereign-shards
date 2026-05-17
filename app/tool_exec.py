# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tool execution and formatting.

Executes tool calls via the registry and formats output for LLM consumption.
"""

from app.agent import ToolRegistry
from app.action import truncate_tool_output

PROCESS_PAUSE_SECONDS = 0.2


def execute_tool(action: dict, registry: ToolRegistry) -> str:
    tool_name = action.get("tool")
    tool_args = action.get("args", [])

    if not tool_name:
        return "[TOOL ERROR] Tool name is missing."
    if not isinstance(tool_args, list):
        return "[TOOL ERROR] Tool args must be a list."

    # Strip wrapping quotes from string args — J often double-quotes
    # patterns like run_search "circuit_breaker" which JSON-parses as
    # the literal string "circuit_breaker" (with quotes), missing all hits.
    tool_args = [
        a[1:-1]
        if isinstance(a, str) and len(a) >= 2
        and a[0] == a[-1] and a[0] in ('"', "'")
        else a
        for a in tool_args
    ]

    result = registry.execute(tool_name, tool_args)
    return truncate_tool_output(result)

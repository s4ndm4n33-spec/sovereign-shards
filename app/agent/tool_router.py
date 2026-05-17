# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
from __future__ import annotations

from typing import Any


def route_tool_call(registry: Any, call: dict[str, Any]) -> dict[str, Any]:
    try:
        if not isinstance(call, dict):
            return {"ok": False, "error": "call must be an object"}
        tool_name = call.get("tool")
        args = call.get("args", {})
        if not isinstance(tool_name, str) or not tool_name:
            return {"ok": False, "error": "tool name is required"}
        if tool_name not in registry:
            return {"ok": False, "error": f"unknown tool: {tool_name}"}
        if not isinstance(args, dict):
            return {"ok": False, "error": "args must be an object"}

        validated = registry.validate(tool_name, args)
        registry.assert_allowed(tool_name)
        handler = registry[tool_name]
        result = handler(validated)
        if isinstance(result, dict) and "ok" in result:
            return result
        return {"ok": True, "output": str(result)}
    except Exception as error:
        return {"ok": False, "error": str(error)}

"""Bootstrap helpers for wiring the next agent layer iteration."""

from __future__ import annotations

from app.agent.tool_registry import ToolRegistry, ToolSpec


def build_default_registry() -> ToolRegistry:
    """Register a safe default tool set backed by `tools/run/*` scripts."""
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="read_file",
            schema={
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string"}},
            },
            side_effect="read",
            timeout_seconds=10,
        )
    )
    registry.register(
        ToolSpec(
            name="write_file",
            schema={
                "type": "object",
                "required": ["path", "content"],
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
            side_effect="write",
            timeout_seconds=20,
        )
    )
    registry.register(
        ToolSpec(
            name="exec_python",
            schema={
                "type": "object",
                "required": ["code"],
                "properties": {"code": {"type": "string"}},
            },
            side_effect="exec",
            timeout_seconds=20,
        )
    )
    registry.register(
        ToolSpec(
            name="scaffold_package",
            schema={
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            },
            side_effect="write",
            timeout_seconds=10,
        )
    )
    return registry

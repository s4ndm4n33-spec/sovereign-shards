"""Schema-validated tool registry scaffolding for the agent runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    """Static metadata for one callable tool."""

    name: str
    schema: dict[str, Any]
    side_effect: str
    timeout_seconds: int = 30
    retries: int = 0


class ToolRegistry:
    """Minimal registry that validates required argument presence."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def validate(self, name: str, args: dict[str, Any]) -> list[str]:
        spec = self.get(name)
        required = spec.schema.get("required", [])
        missing = [key for key in required if key not in args]
        return [f"missing required field: {key}" for key in missing]

    def names(self) -> list[str]:
        return sorted(self._tools)

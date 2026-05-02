"""Tool Registry: Dynamic tool discovery and execution.

Supports:
  1. Built-in tools (Python classes inheriting BaseTool)
  2. External tools (subprocess scripts in tools/run/)
"""
from __future__ import annotations

import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Tuple

from app.agent.contracts import ToolCall


class BaseTool(ABC):
    """Abstract base class for built-in Python tools."""

    name: str = ""
    description: str = ""
    required_args: list[str] = []

    @abstractmethod
    def execute(self, **kwargs) -> Tuple[bool, str]:
        """Execute the tool and return (success, output)."""


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent.parent
        self.tools_dir = self.root / "tools" / "run"
        self.built_in_tools: Dict[str, BaseTool] = {}
        self.external_tools: Dict[str, Path] = {}
        self._refresh_tools()

    def _refresh_tools(self) -> None:
        """Discover and register all external tools."""
        self.external_tools = {}
        if self.tools_dir.exists():
            for file in self.tools_dir.glob("*.py"):
                if not file.name.startswith("_"):
                    self.external_tools[file.stem] = file

    def register_tool(self, tool: BaseTool) -> None:
        """Register a built-in tool."""
        if not tool.name:
            raise ValueError("Tool must have a 'name' attribute")
        self.built_in_tools[tool.name] = tool

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return all registered tools with metadata."""
        tools: Dict[str, Dict[str, Any]] = {}

        for name, tool in self.built_in_tools.items():
            tools[name] = {
                "type": "built-in",
                "description": tool.description,
                "required_args": tool.required_args,
            }

        for name, path in self.external_tools.items():
            tools[name] = {
                "type": "external",
                "description": f"Subprocess tool: {name}",
                "path": str(path.relative_to(self.root)),
            }

        return tools

    def call_tool(self, tool_call: ToolCall) -> Tuple[bool, str]:
        """Execute a tool by name."""
        self._refresh_tools()

        if tool_call.name in self.built_in_tools:
            try:
                return self.built_in_tools[tool_call.name].execute(**tool_call.args)
            except Exception as exc:
                return False, f"[ERROR] {tool_call.name}: {exc}"

        if tool_call.name in self.external_tools:
            return self._call_external_tool(tool_call)

        return False, f"Tool '{tool_call.name}' not found in registry."

    def _call_external_tool(self, tool_call: ToolCall) -> Tuple[bool, str]:
        """Execute an external tool script.

        Args are passed as repeated flags so argparse can parse list values:
          {"libs": ["numpy", "pandas"]} -> --libs numpy pandas
        """
        tool_path = self.external_tools[tool_call.name]

        cmd_parts: list[str] = [sys.executable, str(tool_path)]
        for key, value in tool_call.args.items():
            flag = f"--{key}"
            if isinstance(value, (list, tuple)):
                cmd_parts.append(flag)
                cmd_parts.extend(str(v) for v in value)
            elif isinstance(value, bool):
                if value:
                    cmd_parts.append(flag)
            else:
                cmd_parts.extend([flag, str(value)])

        try:
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.root),
            )
            success = result.returncode == 0
            output = (result.stdout or "").strip()
            error = (result.stderr or "").strip()
            if not success and error:
                output = f"{output}\n{error}".strip()
            return success, (output or "[NO OUTPUT]")
        except subprocess.TimeoutExpired:
            return False, f"[TIMEOUT] Tool '{tool_call.name}' exceeded 60s limit."
        except Exception as exc:
            return False, f"[ERROR] {exc}"

"""Dynamic tool registry for built-in and script-backed tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Callable

from app.file_tools import list_dir, read_file, write_file
from app.system_tools import get_system_snapshot


ToolFn = Callable[..., str]


@dataclass
class ScriptTool:
    name: str
    script_path: Path

    def run(self, *args) -> str:
        str_args = [str(arg) for arg in args]
        stdin_data = ""
        if self.name == "write" and len(str_args) >= 2:
            stdin_data = str_args[1]
            str_args = [str_args[0]]

        try:
            result = subprocess.run(
                [sys.executable, str(self.script_path), *str_args],
                input=stdin_data,
                text=True,
                capture_output=True,
                check=False,
            )
        except Exception as error:
            return f"[TOOL ERROR] Script tool '{self.name}' failed to start: {error}"

        output = (result.stdout or "") + (result.stderr or "")
        output = output.strip()
        if result.returncode != 0:
            return f"[TOOL ERROR] Script tool '{self.name}' exited {result.returncode}: {output}"

        return output or f"[OK] Script tool '{self.name}' completed"


class ToolRegistry:
    """Register built-in Python tools and auto-discover script tools."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.tools: dict[str, ToolFn] = {}
        self._register_builtin_tools()
        self._register_script_tools()

    def _register_builtin_tools(self) -> None:
        self.tools["read_file"] = read_file
        self.tools["write_file"] = write_file
        self.tools["list_dir"] = list_dir
        self.tools["system_snapshot"] = get_system_snapshot

    def _register_script_tools(self) -> None:
        scripts_dir = self.base_dir / "tools" / "run"
        if not scripts_dir.exists():
            return

        for script in sorted(scripts_dir.glob("*.py")):
            name = script.stem
            runner = ScriptTool(name=name, script_path=script)
            self.tools[f"run_{name}"] = runner.run

    def execute(self, tool_name: str, tool_args: list) -> str:
        tool = self.tools.get(tool_name)
        if tool is None:
            known = ", ".join(sorted(self.tools))
            return f"[TOOL ERROR] Unknown tool: {tool_name}. Available: {known}"

        try:
            return str(tool(*tool_args))
        except Exception as error:
            return f"[TOOL ERROR] {tool_name} failed: {error}"

    def describe(self) -> str:
        return "\n".join(f"- {name}" for name in sorted(self.tools))

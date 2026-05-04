"""Dynamic tool registry for built-in and script-backed tools."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable

from app.file_tools import list_dir, read_file, write_file
from app.system_tools import get_system_snapshot

ToolFn = Callable[..., str]


@dataclass
class ToolSpec:
    name: str
    description: str
    args: list[str]


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
        if self.name == "exec" and str_args:
            stdin_data = str_args[0]
            str_args = []

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
        self.specs: dict[str, ToolSpec] = {}
        self._register_builtin_tools()
        self._register_script_tools()

    def _register_tool(self, name: str, fn: ToolFn, description: str, args: list[str]) -> None:
        self.tools[name] = fn
        self.specs[name] = ToolSpec(name=name, description=description, args=args)

    def _register_builtin_tools(self) -> None:
        self._register_tool("read_file", read_file, "Read a file in safe chunks.", ["path", "offset=0", "chunk_bytes=1048576"])
        self._register_tool("write_file", write_file, "Write or append UTF-8 content with 4GB cap.", ["path", "content", "append=false"])
        self._register_tool("list_dir", list_dir, "List directory entries.", ["path"])
        self._register_tool("system_snapshot", get_system_snapshot, "Return local machine snapshot.", [])

    def _load_manifest(self, scripts_dir: Path) -> dict:
        manifest_path = scripts_dir / "registry.json"
        if not manifest_path.exists():
            return {}
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _register_script_tools(self) -> None:
        scripts_dir = self.base_dir / "tools" / "run"
        if not scripts_dir.exists():
            return

        manifest = self._load_manifest(scripts_dir)
        for script in sorted(scripts_dir.glob("*.py")):
            name = script.stem
            tool_name = f"run_{name}"
            runner = ScriptTool(name=name, script_path=script)
            meta = manifest.get(tool_name, {})
            description = meta.get("description", f"Run script tool: {script.name}")
            args = meta.get("args", ["...args"])
            self._register_tool(tool_name, runner.run, description, args)

    def execute(self, tool_name: str, tool_args: list) -> str:
        tool = self.tools.get(tool_name)
        if tool is None:
            known = ", ".join(sorted(self.tools))
            return f"[TOOL ERROR] Unknown tool: {tool_name}. Available: {known}"

        spec = self.specs.get(tool_name)
        if spec and spec.args and len(tool_args) < len([a for a in spec.args if "=" not in a]):
            return f"[TOOL ERROR] {tool_name} expects args {spec.args}; got {tool_args}"

        try:
            return str(tool(*tool_args))
        except Exception as error:
            return f"[TOOL ERROR] {tool_name} failed: {error}"

    def describe(self) -> str:
        rows = []
        for name in sorted(self.tools):
            spec = self.specs.get(name)
            if spec is None:
                rows.append(f"- {name}")
                continue
            sig = f"({', '.join(spec.args)})" if spec.args else "()"
            rows.append(f"- {name}{sig}: {spec.description}")
        return "\n".join(rows)

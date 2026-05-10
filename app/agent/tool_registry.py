from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.agent.script_tool import ScriptTool
from app.agent.tool_schema import ToolSpec, normalize_spec, validate_args
from app.file_tools import list_dir, read_file, write_file
from app.system_tools import get_system_snapshot

ToolCallable = Callable[[dict[str, Any]], dict[str, Any]]


class ToolRegistry:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.tools: dict[str, ToolCallable] = {}
        self.specs: dict[str, ToolSpec] = {}
        self.restrictions: dict[str, bool] = {
            "read": True,
            "write": True,
            "exec": False,
            "network": False,
        }
        self._register_builtin_tools()
        self._register_script_tools()

    def __getitem__(self, name: str) -> ToolCallable:
        return self.tools[name]

    def get(self, name: str, default: Any = None) -> Any:
        return self.tools.get(name, default)

    def __contains__(self, name: str) -> bool:
        return name in self.tools

    def keys(self):
        return self.tools.keys()

    def _register(self, spec: ToolSpec, fn: ToolCallable) -> None:
        self.specs[spec.name] = spec
        self.tools[spec.name] = fn

    def _register_builtin_tools(self) -> None:
        self._register(
            ToolSpec("read_file", "Read a file.", [{"name": "path", "type": "str", "required": True}], "read", 30),
            lambda args: {"ok": True, "output": str(read_file(args["path"]))},
        )
        self._register(
            ToolSpec(
                "write_file",
                "Write a file.",
                [
                    {"name": "path", "type": "str", "required": True},
                    {"name": "content", "type": "str", "required": True},
                ],
                "write",
                30,
            ),
            lambda args: {"ok": True, "output": str(write_file(args["path"], args["content"]))},
        )
        self._register(
            ToolSpec("list_dir", "List directory contents.", [{"name": "path", "type": "str", "required": True}], "read", 30),
            lambda args: {"ok": True, "output": str(list_dir(args["path"]))},
        )
        self._register(
            ToolSpec("system_snapshot", "Get system snapshot.", [], "read", 30),
            lambda args: {"ok": True, "output": str(get_system_snapshot())},
        )

    def _register_script_tools(self) -> None:
        scripts_dir = self.base_dir / "tools" / "run"
        if not scripts_dir.exists():
            return
        manifest: dict[str, Any] = {}
        manifest_path = scripts_dir / "registry.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}

        for script in sorted(scripts_dir.glob("*.py")):
            tool_name = f"run_{script.stem}"
            raw = manifest.get(tool_name, {})
            raw_args = raw.get("args", [])
            args_schema: list[dict[str, Any]] = []
            for index, item in enumerate(raw_args):
                if isinstance(item, dict):
                    args_schema.append(
                        {
                            "name": str(item["name"]),
                            "type": str(item.get("type", "str")),
                            "required": bool(item.get("required", True)),
                            **({"default": item["default"]} if "default" in item else {}),
                        }
                    )
                else:
                    args_schema.append({"name": str(item), "type": "str", "required": True})
            spec = ToolSpec(
                name=tool_name,
                description=str(raw.get("description", f"Run script {script.stem}.")),
                args=args_schema,
                side_effect=str(raw.get("side_effect", "exec")),
                timeout_seconds=int(raw.get("timeout_seconds", 30)),
            )
            wrapper = ScriptTool(tool_name, script, spec)
            self._register(spec, wrapper.run)

    def schema(self, tool_name: str) -> dict[str, Any]:
        spec = self.specs[tool_name]
        return normalize_spec(spec)

    def validate(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        return validate_args(self.specs[tool_name], args)

    def get_side_effect(self, tool_name: str) -> str:
        spec = self.specs.get(tool_name)
        return spec.side_effect if spec else "exec"

    def assert_allowed(self, tool_name: str) -> None:
        effect = self.get_side_effect(tool_name)
        allowed = self.restrictions.get(effect, False)
        if not allowed:
            raise PermissionError(f"side effect '{effect}' is blocked for tool '{tool_name}'")

    def as_prompt_block(self) -> str:
        lines = ["TOOLS:"]
        for name in sorted(self.specs):
            spec = self.specs[name]
            args_text = ", ".join(f"{a['name']}: {a['type']}" for a in spec.args)
            lines.append(f"- {name}({args_text}) [{spec.side_effect}] — {spec.description}")
        return "\n".join(lines)

    def describe(self) -> str:
        return self.as_prompt_block()

    def execute(self, tool_name: str, tool_args: list) -> str:
        try:
            spec = self.specs[tool_name]
        except KeyError:
            return json.dumps({"ok": False, "error": f"[TOOL ERROR] Unknown tool: {tool_name}"}, ensure_ascii=True, sort_keys=True)
        mapped: dict[str, Any] = {}
        for index, arg_spec in enumerate(spec.args):
            if index < len(tool_args):
                mapped[arg_spec["name"]] = tool_args[index]
        from app.agent.tool_router import route_tool_call

        result = route_tool_call(self, {"tool": tool_name, "args": mapped})
        return json.dumps(result, ensure_ascii=True, sort_keys=True)

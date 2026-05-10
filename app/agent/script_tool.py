from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from app.agent.tool_schema import ToolSpec


class ScriptTool:
    def __init__(self, name: str, script_path: Path, spec: ToolSpec) -> None:
        self.name = name
        self.script_path = script_path
        self.spec = spec

    def run(self, args: dict[str, Any] | None = None, *legacy_args: Any) -> dict[str, Any] | str:
        legacy_mode = not isinstance(args, dict)
        mapped: dict[str, Any] = {}
        if legacy_mode:
            values: list[Any] = []
            if args is not None:
                values.append(args)
            values.extend(legacy_args)
            normalized = [a if isinstance(a, dict) else {"name": str(a), "type": "str", "required": True} for a in self.spec.args]
            for index, arg_spec in enumerate(normalized):
                if index < len(values):
                    mapped[arg_spec["name"]] = values[index]
        else:
            mapped = args

        cli_args: list[str] = []
        stdin_value: str = ""
        normalized = [a if isinstance(a, dict) else {"name": str(a), "type": "str", "required": True} for a in self.spec.args]
        for arg in normalized:
            key = arg["name"]
            value = mapped.get(key)
            if key == "stdin":
                stdin_value = "" if value is None else str(value)
            elif value is not None:
                cli_args.append(str(value))

        try:
            result = subprocess.run([sys.executable, str(self.script_path), *cli_args], input=stdin_value, text=True, capture_output=True, timeout=self.spec.timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            err = f"tool '{self.spec.name}' timed out after {self.spec.timeout_seconds}s"
            return f"[TOOL ERROR] {err}" if legacy_mode else {"ok": False, "error": err}
        except Exception as error:
            err = f"tool '{self.spec.name}' failed: {error}"
            return f"[TOOL ERROR] {err}" if legacy_mode else {"ok": False, "error": err}

        output = ((result.stdout or "") + (result.stderr or "")).strip()
        if result.returncode != 0:
            err = output or f"tool exited {result.returncode}"
            return f"[TOOL ERROR] {err}" if legacy_mode else {"ok": False, "error": err}

        if legacy_mode:
            return output
        if not output:
            return {"ok": True, "output": ""}
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict) and "ok" in parsed:
                return parsed
        except Exception:
            pass
        return {"ok": True, "output": output}

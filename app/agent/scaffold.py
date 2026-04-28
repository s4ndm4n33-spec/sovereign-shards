from __future__ import annotations
import os
from pathlib import Path
from .contracts import ToolCall, ToolResult

class ToolRegistry:
    def __init__(self):
        # UNIVERSAL ANCHOR: Find the root relative to this file's location
        # app/agent/scaffold.py -> go up 2 levels to get to the root
        self.root = Path(__file__).resolve().parent.parent.parent
        self.tools_dir = self.root / "tools" / "run"
        
        self.registry = {
            "exec": self.tools_dir / "exec.py",
            "read": self.tools_dir / "read.py",
            "write": self.tools_dir / "write.py",
            "scaffold": self.tools_dir / "scaffold.py"
        }

    def dispatch(self, call: ToolCall) -> str:
        if call.name not in self.registry:
            raise ValueError(f"Unknown tool: {call.name}")
        
        # .as_posix() ensures forward slashes even on Windows for consistency
        # wrapping in quotes handles any spaces in the directory names
        script_path = f'"{self.registry[call.name].as_posix()}"'
        
        if call.name == "exec":
            return f"python {script_path}"
        
        args_str = " ".join([f'"{v}"' if " " in str(v) else str(v) for v in call.args.values()])
        return f"python {script_path} {args_str}"

def get_registry() -> ToolRegistry:
    return ToolRegistry()

def build_default_registry() -> ToolRegistry:
    return ToolRegistry()

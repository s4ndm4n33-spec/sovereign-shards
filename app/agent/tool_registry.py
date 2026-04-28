import os
import subprocess
from pathlib import Path
from typing import Tuple
from app.agent.contracts import ToolCall

class ToolRegistry:
    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent.parent
        self.tools_dir = self.root / "tools" / "run"
        self._refresh_tools()

    def _refresh_tools(self):
        """Map all .py files in tools/run to the registry."""
        self.tools = {}
        if self.tools_dir.exists():
            for f in self.tools_dir.glob("*.py"):
                self.tools[f.stem] = f

    def call_tool(self, tool_call: ToolCall) -> Tuple[bool, str]:
        self._refresh_tools() # Ensure new tools are picked up
        if tool_call.name not in self.tools:
            return False, f"Tool '{tool_call.name}' not in registry."
        
        tool_path = self.tools[tool_call.name]
        # Format arguments for the command line
        arg_str = " ".join([f"--{k}=\"{v}\"" for k, v in tool_call.args.items()])
        
        import sys
        cmd = f'"{sys.executable}" "{tool_path}" {arg_str}'
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            success = (result.returncode == 0)
            output = result.stdout if success else result.stderr
            return success, output
        except Exception as e:
            return False, str(e)

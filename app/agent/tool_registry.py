"""Tool Registry: Dynamic tool discovery and execution.

Supports:
  1. Built-in tools (Python classes inheriting BaseTool)
  2. External tools (subprocess scripts in tools/run/)
"""
import os
import sys
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Dict, Any

from app.agent.contracts import ToolCall


class BaseTool(ABC):
    """Abstract base class for all tools.
    
    Subclass this to add a built-in tool to the registry:
    
        class MyTool(BaseTool):
            name = "my_tool"
            description = "Does something useful"
            
            def execute(self, **kwargs) -> Tuple[bool, str]:
                # Your logic here
                return True, "Result"
    """
    name: str = ""
    description: str = ""
    required_args: list = []

    @abstractmethod
    def execute(self, **kwargs) -> Tuple[bool, str]:
        """Execute the tool.
        
        Returns:
            (success: bool, output: str)
        """
        pass


class ToolRegistry:
    """Central registry for all available tools.
    
    Discovery:
      - Scans tools/run/*.py for external tool scripts
      - Maintains a dict of built-in BaseTool subclasses
    
    Execution:
      - call_tool(ToolCall) routes to either built-in or external
    """

    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent.parent
        self.tools_dir = self.root / "tools" / "run"
        self.built_in_tools: Dict[str, BaseTool] = {}
        self.external_tools: Dict[str, Path] = {}
        self._refresh_tools()

    def _refresh_tools(self):
        """Discover and register all available tools."""
        # External tools: scan tools/run/*.py
        self.external_tools = {}
        if self.tools_dir.exists():
            for f in self.tools_dir.glob("*.py"):
                if not f.name.startswith("_"):
                    self.external_tools[f.stem] = f

    def register_tool(self, tool: BaseTool) -> None:
        """Register a built-in tool.
        
        Usage:
            registry = ToolRegistry()
            registry.register_tool(MyTool())
        """
        if not tool.name:
            raise ValueError("Tool must have a 'name' attribute")
        self.built_in_tools[tool.name] = tool

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return all registered tools with metadata."""
        tools = {}
        
        # Built-in tools
        for name, tool in self.built_in_tools.items():
            tools[name] = {
                "type": "built-in",
                "description": tool.description,
                "required_args": tool.required_args,
            }
        
        # External tools
        for name in self.external_tools:
            tools[name] = {
                "type": "external",
                "description": f"Subprocess tool: {name}",
            }
        
        return tools

    def call_tool(self, tool_call: ToolCall) -> Tuple[bool, str]:
        """Execute a tool by name.
        
        Args:
            tool_call: ToolCall(name="...", args={...})
        
        Returns:
            (success: bool, output: str)
        """
        self._refresh_tools()  # Ensure new tools are picked up

        # Check built-in tools first
        if tool_call.name in self.built_in_tools:
            try:
                tool = self.built_in_tools[tool_call.name]
                return tool.execute(**tool_call.args)
            except Exception as e:
                return False, f"[ERROR] {tool_call.name}: {str(e)}"

        # Check external tools
        if tool_call.name in self.external_tools:
            return self._call_external_tool(tool_call)

        return False, f"Tool '{tool_call.name}' not found in registry."

    def _call_external_tool(self, tool_call: ToolCall) -> Tuple[bool, str]:
        """Execute an external tool script.
        
        Convention:
          External tools are invoked with arguments as CLI flags:
            python tools/run/mytool.py --arg1="value1" --arg2="value2"
        """
        tool_path = self.external_tools[tool_call.name]
        
        # Build command line
        arg_str = " ".join([f'--{k}="{v}"' for k, v in tool_call.args.items()])
        cmd = f'"{sys.executable}" "{tool_path}" {arg_str}'.strip()

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            success = result.returncode == 0
            output = result.stdout if success else result.stderr
            return success, output
        except subprocess.TimeoutExpired:
            return False, f"[TIMEOUT] Tool '{tool_call.name}' exceeded 30s limit."
        except Exception as e:
            return False, f"[ERROR] {str(e)}"

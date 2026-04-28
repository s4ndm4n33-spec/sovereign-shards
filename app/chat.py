from __future__ import annotations
import re
import subprocess
from dataclasses import dataclass
from .agent.contracts import ToolCall
from .agent.scaffold import build_default_registry

@dataclass
class ChatSession:
    model: str
    system_prompt: str
    
    def __post_init__(self):
        self.registry = build_default_registry()

    def _run_turn(self, user_input: str) -> str:
        # Pattern to catch the execute tag
        pattern = r"\[EXECUTE:\s*(.*?)\]"
        match = re.search(pattern, user_input, re.DOTALL)
        
        if match:
            code = match.group(1).strip()
            # Create a formal ToolCall
            call = ToolCall(name="exec", args={"code": code})
            # Dispatch to the Registry for the correct hardware-agnostic command
            cmd = self.registry.dispatch(call)
            
            try:
                # Use the 'exec' tool pattern: pass code via stdin
                process = subprocess.Popen(
                    cmd, 
                    shell=True, 
                    stdin=subprocess.PIPE, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate(input=code)
                observation = stdout + stderr
                return f"\n[SYSTEM: Executing Bridge...]\n[OBSERVATION]:\n{observation.strip()}"
            except Exception as e:
                return f"\n[SYSTEM: Bridge Error]: {str(e)}"
        
        return "No execution command found."

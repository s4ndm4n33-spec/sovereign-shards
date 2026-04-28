import time
from pathlib import Path
from app.agent.contracts import AgentTask, ToolCall, ToolResult
from app.agent.tool_registry import ToolRegistry

class HamiltonExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.root = Path(__file__).resolve().parent.parent.parent

    def execute_step(self, task: AgentTask, step_idx: int) -> ToolResult:
        step = task.steps[step_idx]
        tool_call = ToolCall(name=step['tool'], args=step['args'])
        internal_id = f"{task.task_id}_{step_idx}"

        success, output = self.registry.call_tool(tool_call)
        result = ToolResult(call_id=internal_id, success=success, output=output)

        # Post-write verification
        if result.success and tool_call.name == "write":
            if not self._verify(tool_call):
                result.success = False
                result.output += "\n[HAMILTON_ERROR]: Physical verify failed. Hardware latency exceeded."
        return result

    def _verify(self, call: ToolCall) -> bool:
        path_str = call.args.get('path', '')
        if not path_str: return False
        
        path = Path(path_str)
        target = path if path.is_absolute() else self.root / path
        
        # Extended Polling for Kingston 2.0
        for _ in range(5): 
            if target.exists(): 
                return True
            time.sleep(1.0) # Settle window for FAT32
        return False

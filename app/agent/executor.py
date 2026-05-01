"""Hamilton Executor: Manages execution of agent tasks.

Responsibilities:
  - Execute individual steps via tool registry
  - Verify write operations (FAT32 latency tolerance)
  - Maintain execution context
  - Batch execution for multi-step tasks
"""
import time
from pathlib import Path
from typing import List

from app.agent.contracts import AgentTask, ToolCall, ToolResult, ExecutionContext
from app.agent.tool_registry import ToolRegistry


class HamiltonExecutor:
    """Executes agent tasks with reliability and verification.
    
    Named after Alexander Hamilton: "assume failure is default state."
    Enforces write verification and error handling.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.root = Path(__file__).resolve().parent.parent.parent

    def execute_step(self, task: AgentTask, step_idx: int) -> ToolResult:
        """Execute a single task step.
        
        Args:
            task: The AgentTask containing steps
            step_idx: Index of the step to execute
        
        Returns:
            ToolResult with success flag and output
        """
        if step_idx < 0 or step_idx >= len(task.steps):
            return ToolResult(
                call_id=f"{task.task_id}_{step_idx}",
                success=False,
                output="",
                error=f"Invalid step index: {step_idx}"
            )

        step = task.steps[step_idx]
        tool_call = ToolCall(name=step["tool"], args=step.get("args", {}))
        internal_id = f"{task.task_id}_{step_idx}"

        # Execute via registry
        success, output = self.registry.call_tool(tool_call)
        result = ToolResult(
            call_id=internal_id,
            success=success,
            output=output
        )

        # Post-write verification (Hamilton principle: verify writes)
        if result.success and tool_call.name == "write":
            if not self._verify_write(tool_call):
                result.success = False
                result.output += "\n[HAMILTON_VERIFY]: Physical write verification failed. FAT32 latency exceeded."

        return result

    def execute_plan(self, task: AgentTask, context: ExecutionContext = None) -> List[ToolResult]:
        """Execute all steps in a task.
        
        Args:
            task: The AgentTask with steps
            context: Optional ExecutionContext (will be created if None)
        
        Returns:
            List of ToolResults for all executed steps
        """
        if context is None:
            context = ExecutionContext(task=task)

        for i in range(len(task.steps)):
            result = self.execute_step(task, i)
            context.results.append(result)
            
            # If any step fails and it's critical, optionally stop
            # (For now, continue regardless)

        return context.results

    def _verify_write(self, call: ToolCall, timeout_seconds: int = 5) -> bool:
        """Verify that a write operation actually persisted to disk.
        
        Handles FAT32 latency by polling with exponential backoff.
        Used for USB and embedded storage reliability.
        
        Args:
            call: The ToolCall that performed the write
            timeout_seconds: Total time to wait for file to appear
        
        Returns:
            True if file exists and is readable, False if timeout
        """
        path_str = call.args.get("path", "")
        if not path_str:
            return False

        path = Path(path_str)
        target = path if path.is_absolute() else self.root / path

        # Extended polling for FAT32 settle window
        start = time.time()
        poll_interval = 0.1  # Start at 100ms

        while time.time() - start < timeout_seconds:
            if target.exists():
                try:
                    # Try to read to verify it's actually writable
                    with open(target, "rb") as f:
                        _ = f.read(1)
                    return True
                except (OSError, IOError):
                    pass
            
            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 1.0)  # Exponential backoff, max 1s

        return False

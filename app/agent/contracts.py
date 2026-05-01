"""Agent Contracts: Data model for tasks, tools, and execution."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
from datetime import datetime


class TaskStatus(Enum):
    """Lifecycle states for an AgentTask."""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ToolCall:
    """Contract: Tool invocation."""
    name: str
    args: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "args": self.args}


@dataclass
class ToolResult:
    """Contract: Tool execution result."""
    call_id: str
    success: bool
    output: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "success": self.success,
            "output": self.output,
            "timestamp": self.timestamp,
            "error": self.error,
        }


@dataclass
class AgentStep:
    """Contract: Single execution step."""
    step_id: str
    tool: str
    args: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[ToolResult] = None


@dataclass
class AgentTask:
    """Contract: Decomposed goal with executable steps."""
    task_id: str
    goal: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    checkpoint_file: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "steps": self.steps,
            "status": self.status,
            "checkpoint_file": self.checkpoint_file,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass
class ExecutionContext:
    """Contract: Runtime context passed through execution pipeline."""
    task: AgentTask
    results: List[ToolResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_sandboxed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

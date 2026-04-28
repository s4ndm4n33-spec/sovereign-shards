from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class ToolCall:
    name: str
    args: Dict[str, Any]

@dataclass
class ToolResult:
    call_id: str
    success: bool
    output: str

@dataclass
class AgentStep:
    step_id: str
    tool: str
    args: Dict[str, Any]

@dataclass
class AgentTask:
    task_id: str
    goal: str
    steps: List[Dict[str, Any]]
    status: str = "pending"
    checkpoint_file: Optional[str] = None

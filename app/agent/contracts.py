"""Core contracts for the upcoming planner/executor agent layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AutonomyMode = Literal["manual", "semi", "auto-safe", "auto-full"]


@dataclass(frozen=True)
class AgentStep:
    """One planned step with a deterministic success signal."""

    id: str
    goal: str
    success_criteria: str
    depends_on: tuple[str, ...] = ()  # IDs of prerequisite steps


@dataclass(frozen=True)
class ToolCall:
    """Validated tool invocation emitted by planner/executor stages."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Standardized outcome for tool invocations."""

    name: str
    ok: bool
    output: str
    error: str = ""


@dataclass
class AgentTask:
    """Checkpointable task state for planner/executor/verifier flows."""

    objective: str
    mode: AutonomyMode = "manual"
    steps: list[AgentStep] = field(default_factory=list)
    completed_step_ids: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

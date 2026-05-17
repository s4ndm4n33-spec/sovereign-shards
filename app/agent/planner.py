# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Planner: decompose a user objective into executable AgentSteps.

The planner asks the LLM to break a task into small, concrete steps,
each with a success criterion. It parses the response into AgentStep objects.
If parsing fails, it falls back to a single-step plan.

Also handles forge detection: when a request implies a capability J lacks,
the planner injects forge steps (research → generate → validate → register)
ahead of the normal task steps.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, TYPE_CHECKING

from app.agent.contracts import AgentStep, AgentTask, AutonomyMode
from app.agent.tool_researcher import needs_new_tool, ToolSpec

if TYPE_CHECKING:
    from app.agent.tool_registry import ToolRegistry


PLAN_PROMPT = """You are a coding-agent planner. Given a user objective, break it into
small, concrete steps. Each step MUST have:
- id: short slug (e.g. "step_1")
- goal: what to do in one sentence
- success_criteria: how to verify it worked
- depends_on: list of step IDs that must finish first (empty list if none)

Steps with no dependencies can run in parallel. Use depends_on to express ordering.

Respond with ONLY a JSON array of objects. No prose, no markdown fences.
Example:
[{{"id": "step_1", "goal": "Read the README", "success_criteria": "File content is loaded", "depends_on": []}},
 {{"id": "step_2", "goal": "Fix the bug in main.py", "success_criteria": "Tests pass", "depends_on": ["step_1"]}}]

User objective: {objective}
"""


def build_plan_prompt(objective: str) -> str:
    """Build the system prompt for the planner."""
    return PLAN_PROMPT.format(objective=objective)


def check_forge_needed(
    objective: str,
    registry: "ToolRegistry",
) -> bool:
    """Quick check: does this objective need the tool forge?

    Call this before planning.  If True, the caller should run the
    forge pipeline (research → generate → validate → register) and
    then re-plan with the new tools available.
    """
    return needs_new_tool(objective, registry)


def parse_plan(raw: str, objective: str, mode: AutonomyMode = "semi") -> AgentTask:
    """Parse LLM planner output into an AgentTask.

    Falls back to a single-step plan if parsing fails.
    """
    steps = _try_parse_steps(raw)
    if not steps:
        # Fallback: treat the whole objective as one step
        steps = [AgentStep(
            id="step_1",
            goal=objective,
            success_criteria="User confirms completion.",
        )]

    return AgentTask(
        objective=objective,
        mode=mode,
        steps=steps,
    )


def _try_parse_steps(raw: str) -> list[AgentStep]:
    """Try to extract a JSON array of steps from LLM output."""
    # Strip markdown fences if present
    cleaned = re.sub(r"```json?\s*", "", raw)
    cleaned = re.sub(r"```", "", cleaned).strip()

    # Try to find a JSON array
    match = re.search(r"\[.*\]", cleaned, flags=re.S)
    if not match:
        return []

    try:
        items: list[dict[str, Any]] = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    if not isinstance(items, list):
        return []

    steps = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        step_id = item.get("id", f"step_{i + 1}")
        goal = item.get("goal", "")
        criteria = item.get("success_criteria", "Completed.")
        raw_deps = item.get("depends_on", [])
        depends_on = tuple(d for d in raw_deps if isinstance(d, str))
        if goal:
            steps.append(AgentStep(
                id=step_id, goal=goal,
                success_criteria=criteria, depends_on=depends_on,
            ))

    return steps

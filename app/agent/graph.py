# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Task graph: topological execution of AgentSteps with dependencies.

Steps declare depends_on (tuple of step IDs).  The graph walker yields
steps in valid execution order, grouping independent steps into tiers.
"""

from __future__ import annotations

from collections import deque

from app.agent.contracts import AgentStep


def topo_tiers(steps: list[AgentStep]) -> list[list[AgentStep]]:
    """Group steps into topological tiers (Kahn's algorithm).

    Each tier contains steps whose dependencies are all satisfied by
    previous tiers.  Steps within a tier are independent.

    Raises ValueError on cycles.
    """
    if not steps:
        return []

    by_id: dict[str, AgentStep] = {s.id: s for s in steps}
    in_degree: dict[str, int] = {s.id: 0 for s in steps}
    dependents: dict[str, list[str]] = {s.id: [] for s in steps}

    for step in steps:
        for dep_id in step.depends_on:
            if dep_id in by_id:
                in_degree[step.id] += 1
                dependents[dep_id].append(step.id)

    tiers: list[list[AgentStep]] = []
    queue = deque(sid for sid, deg in in_degree.items() if deg == 0)
    visited = 0

    while queue:
        tier: list[AgentStep] = []
        next_queue: list[str] = []
        while queue:
            sid = queue.popleft()
            tier.append(by_id[sid])
            visited += 1
            for dep_sid in dependents[sid]:
                in_degree[dep_sid] -= 1
                if in_degree[dep_sid] == 0:
                    next_queue.append(dep_sid)
        tiers.append(tier)
        queue = deque(next_queue)

    if visited != len(steps):
        raise ValueError(
            f"Cycle detected in task graph ({visited}/{len(steps)} reachable)"
        )
    return tiers


def ready_steps(steps: list[AgentStep], completed: set[str]) -> list[AgentStep]:
    """Return steps whose deps are all in the completed set (and not done)."""
    return [
        s for s in steps
        if s.id not in completed
        and all(d in completed for d in s.depends_on)
    ]


def format_graph(steps: list[AgentStep], completed: set[str] | None = None) -> str:
    """Pretty-print the task graph."""
    if completed is None:
        completed = set()
    lines: list[str] = []
    for step in steps:
        marker = "✓" if step.id in completed else "○"
        deps = f" (after: {', '.join(step.depends_on)})" if step.depends_on else ""
        lines.append(f"  {marker} {step.id}: {step.goal}{deps}")
    return "\n".join(lines)

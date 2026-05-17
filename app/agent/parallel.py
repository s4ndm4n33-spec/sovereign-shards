# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Parallel step execution within task graph tiers.

Steps within the same tier are independent (no mutual dependencies).
This module runs them concurrently using ThreadPoolExecutor.

USB-safe: bounded thread count, timeouts, graceful error capture.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

from app.agent.contracts import AgentStep

# Cap at 3 threads — USB 2.0 I/O is the bottleneck, not CPU.
# More threads would just thrash the Kingston's flash controller.
MAX_WORKERS = 3


@dataclass
class StepOutcome:
    """Result of executing and verifying one step."""
    step: AgentStep
    reply: str
    passed: bool
    reason: str
    error: str | None = None


# Print lock so parallel step output doesn't interleave
_print_lock = threading.Lock()


def safe_print(*args, **kwargs) -> None:
    """Thread-safe print."""
    with _print_lock:
        print(*args, **kwargs)


def run_tier_parallel(
    tier_steps: list[AgentStep],
    execute_fn: Callable[[AgentStep], StepOutcome],
    max_workers: int = MAX_WORKERS,
) -> list[StepOutcome]:
    """Execute a tier of independent steps in parallel.

    Args:
        tier_steps: Steps that have no mutual dependencies (same topo tier).
        execute_fn: Callback that runs one step end-to-end (execute + verify).
                    Must be thread-safe and return a StepOutcome.
        max_workers: Max concurrent threads.

    Returns:
        List of StepOutcome in completion order.
    """
    if len(tier_steps) <= 1:
        # No point spinning up a pool for a single step
        return [execute_fn(tier_steps[0])] if tier_steps else []

    workers = min(max_workers, len(tier_steps))
    outcomes: list[StepOutcome] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_step = {
            pool.submit(execute_fn, step): step
            for step in tier_steps
        }

        for future in as_completed(future_to_step):
            step = future_to_step[future]
            try:
                outcome = future.result(timeout=300)
                outcomes.append(outcome)
            except Exception as exc:
                outcomes.append(StepOutcome(
                    step=step,
                    reply="",
                    passed=False,
                    reason=f"Execution error: {exc}",
                    error=str(exc),
                ))

    return outcomes

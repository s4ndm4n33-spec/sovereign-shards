"""Self-healing circuit breaker for stuck agent loops.

Detects repetitive patterns that indicate the agent is stuck:
  - Same tool+args called N times in a row
  - Same error message repeating
  - Step consuming too many turns without progress
  - Total turn budget exhausted

When tripped, the breaker injects a recovery prompt or forces a step skip.
"""

from __future__ import annotations

import time
from collections import deque

from app import personality as persona
from dataclasses import dataclass, field


# ── Configuration ─────────────────────────────────────────────────────

MAX_REPEAT_CALLS = 3     # Same tool+args this many times → stuck
MAX_REPEAT_ERRORS = 3    # Same error text this many times → stuck
MAX_STEP_TURNS = 12      # Turns within one step before forced exit
MAX_TOTAL_TURNS = 60     # Total turns across all steps
COOLDOWN_SECONDS = 2.0   # Pause between recovery attempts


# ── Data ──────────────────────────────────────────────────────────────

@dataclass
class TurnRecord:
    """Record of a single agent turn for pattern detection."""
    tool: str
    args_hash: str
    output_prefix: str   # First 200 chars for error matching
    is_error: bool
    timestamp: float = field(default_factory=time.time)


@dataclass
class BreakerState:
    """Mutable state for the circuit breaker across a task."""
    total_turns: int = 0
    step_turns: int = 0
    recent: deque[TurnRecord] = field(default_factory=lambda: deque(maxlen=20))
    trips: int = 0        # How many times the breaker has tripped
    last_trip: float = 0.0


class CircuitBreaker:
    """Monitor agent loop for stuck patterns and inject recovery."""

    def __init__(self, tool_budget: int = 3) -> None:
        self.state = BreakerState()
        # Scale step limit with budget so heavy pipelines aren't killed early
        self.max_step_turns = MAX_STEP_TURNS + max(0, tool_budget - 3)

    def reset_step(self) -> None:
        """Call at the start of each new step."""
        self.state.step_turns = 0

    def record_turn(
        self,
        tool: str = "",
        args: str = "",
        output: str = "",
        is_error: bool = False,
    ) -> None:
        """Record a turn for pattern analysis."""
        self.state.total_turns += 1
        self.state.step_turns += 1
        self.state.recent.append(TurnRecord(
            tool=tool,
            args_hash=str(hash(args)),
            output_prefix=output[:200],
            is_error=is_error,
        ))

    def check(self) -> BreakerTrip | None:
        """Check if any stuck pattern is detected.

        Returns None if healthy, or a BreakerTrip with recovery info.
        """
        # 1. Total budget exceeded
        if self.state.total_turns >= MAX_TOTAL_TURNS:
            return self._trip("budget_exceeded",
                persona.breaker_budget_exceeded(self.state.total_turns, MAX_TOTAL_TURNS))

        # 2. Step turn limit (scales with tool_budget via __init__)
        if self.state.step_turns >= self.max_step_turns:
            return self._trip("step_stuck",
                persona.breaker_step_stuck(self.state.step_turns))

        # 3. Repeated tool calls (same tool + same args)
        if len(self.state.recent) >= MAX_REPEAT_CALLS:
            last_n = list(self.state.recent)[-MAX_REPEAT_CALLS:]
            if (all(r.tool == last_n[0].tool for r in last_n)
                    and all(r.args_hash == last_n[0].args_hash for r in last_n)
                    and last_n[0].tool):
                return self._trip("repeat_call",
                    persona.breaker_repeat_call(last_n[0].tool, MAX_REPEAT_CALLS))

        # 4. Repeated errors
        if len(self.state.recent) >= MAX_REPEAT_ERRORS:
            recent_errors = [r for r in list(self.state.recent)[-MAX_REPEAT_ERRORS:]
                             if r.is_error]
            if len(recent_errors) >= MAX_REPEAT_ERRORS:
                prefixes = [r.output_prefix for r in recent_errors]
                if len(set(prefixes)) == 1:
                    return self._trip("repeat_error",
                        persona.breaker_repeat_error(MAX_REPEAT_ERRORS))

        return None

    def _trip(self, reason: str, message: str) -> "BreakerTrip":
        """Record a trip and return recovery info."""
        self.state.trips += 1
        self.state.last_trip = time.time()
        return BreakerTrip(reason=reason, message=message, trip_count=self.state.trips)

    @property
    def is_healthy(self) -> bool:
        """Quick health check."""
        return self.check() is None

    def stats(self) -> dict:
        """Return breaker statistics for logging."""
        return {
            "total_turns": self.state.total_turns,
            "step_turns": self.state.step_turns,
            "trips": self.state.trips,
            "recent_tools": [r.tool for r in self.state.recent if r.tool],
        }


@dataclass
class BreakerTrip:
    """Information about a circuit breaker trip."""
    reason: str     # "repeat_call" | "repeat_error" | "step_stuck" | "budget_exceeded"
    message: str    # Recovery prompt to inject
    trip_count: int

    @property
    def should_force_skip(self) -> bool:
        """After multiple trips on the same step, force-skip it."""
        return self.trip_count >= 3 or self.reason == "budget_exceeded"

    @property
    def recovery_prompt(self) -> str:
        """The prompt to inject into the conversation."""
        prefix = "[CIRCUIT BREAKER]" if self.trip_count < 3 else f"[CIRCUIT BREAKER] {persona.breaker_force_skip()}"
        return f"{prefix} {self.message}"

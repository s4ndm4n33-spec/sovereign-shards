# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""File-based task buffer for plan/execute mode.

Steps are stored as JSONL on disk, outside the context window.
The planner writes steps, the executor pops and runs them one at a time.
The buffer lives *outside context*, so J's 2048 tokens are spent on the
current step only.

USB-safe: atomic writes via .tmp + os.replace + fsync.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = BASE_DIR / "memory"
BUFFER_PATH = MEMORY_DIR / "task_buffer.jsonl"
MAX_STEPS = 10  # 7B models produce garbage beyond ~10 steps


def _ensure_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


# ── Write / Read ──────────────────────────────────────────────────


def write_plan(steps: list[dict]) -> int:
    """Write a fresh plan to the buffer. Overwrites any existing plan.

    Returns the number of steps written (capped at MAX_STEPS).
    """
    _ensure_dir()
    capped = steps[:MAX_STEPS]
    tmp = str(BUFFER_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for step in capped:
            step.setdefault("status", "pending")
            step.setdefault("result", "")
            step.setdefault("ts", None)
            f.write(json.dumps(step, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, str(BUFFER_PATH))
    return len(capped)


def read_all() -> list[dict]:
    """Read all entries from the buffer."""
    if not BUFFER_PATH.exists():
        return []
    entries: list[dict] = []
    try:
        with open(BUFFER_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return []
    return entries


def next_step() -> dict | None:
    """Return the next pending step, or None if all done/failed."""
    steps = read_all()
    done_ids = {s["id"] for s in steps if s["status"] == "done"}
    for step in steps:
        if step["status"] == "pending":
            deps = step.get("depends", [])
            if all(d in done_ids for d in deps):
                return step
    return None


def mark_done(step_id: str, result: str) -> None:
    """Mark a step as completed with its result."""
    _update_status(step_id, "done", result)


def mark_failed(step_id: str, error: str) -> None:
    """Mark a step as failed."""
    _update_status(step_id, "failed", error)


def is_complete() -> bool:
    """True when all steps are done or the plan is empty."""
    steps = read_all()
    if not steps:
        return True
    return all(s["status"] in ("done", "failed") for s in steps)


def pending_count() -> int:
    """Number of steps still pending."""
    return sum(1 for s in read_all() if s["status"] == "pending")


def done_count() -> int:
    """Number of completed steps."""
    return sum(1 for s in read_all() if s["status"] == "done")


def failed_count() -> int:
    """Number of failed steps."""
    return sum(1 for s in read_all() if s["status"] == "failed")


# ── Summary ───────────────────────────────────────────────────────


def summary() -> str:
    """Return a compact summary of all steps and their results.

    Designed for injection into context — kept under ~500 chars.
    """
    steps = read_all()
    if not steps:
        return "[TASK BUFFER] Empty — no plan loaded."
    lines = [f"[TASK BUFFER] {len(steps)} steps:"]
    for s in steps:
        icon = "✓" if s["status"] == "done" else "✗" if s["status"] == "failed" else "…"
        lines.append(f"  {icon} {s['id']}: {s['goal']}")
        if s.get("result"):
            # Cap result length to protect context
            result_preview = s["result"][:120].replace("\n", " ")
            lines.append(f"    → {result_preview}")
    return "\n".join(lines)


def step_prompt(step: dict) -> str:
    """Build a focused prompt for a single step.

    This is what gets injected into J's context — system + this prompt.
    Keeps it minimal to fit 2048 tokens.
    """
    step_id = step.get("id", "?")
    goal = step.get("goal", "")
    deps = step.get("depends", [])

    parts = [
        f"[CURRENT STEP — {step_id}]",
        f"Goal: {goal}",
    ]

    # Include results from dependencies (compact)
    if deps:
        all_steps = read_all()
        dep_map = {s["id"]: s for s in all_steps}
        for dep_id in deps:
            dep = dep_map.get(dep_id)
            if dep and dep.get("result"):
                result_preview = dep["result"][:100].replace("\n", " ")
                parts.append(f"Previous ({dep_id}): {result_preview}")

    parts.append("")
    parts.append("Call ONE tool to accomplish this step. After the result, "
                 "state what you found or did in one sentence.")

    return "\n".join(parts)


# ── Parsing ───────────────────────────────────────────────────────


def parse_numbered_plan(text: str) -> list[dict]:
    """Extract numbered steps from text (LLM output or user input).

    Handles formats like:
        1. Read the router code
        2. Add the new route
        3. Test it

    Also handles:
        1) Read the router code
        Step 1: Read the router code
        1 — Read the router code
    """
    steps: list[dict] = []
    # Match: "1. ...", "1) ...", "Step 1: ...", "1 - ...", "1 — ..."
    for match in re.finditer(
        r"^(?:step\s*)?\d+\s*[\.\)\:\-\u2014\u2013]\s*(.+)$", text, re.MULTILINE | re.IGNORECASE
    ):
        step_id = f"s{len(steps) + 1}"
        goal = match.group(1).strip()
        if not goal or len(goal) < 3:
            continue
        depends = [f"s{len(steps)}"] if steps else []
        steps.append({
            "id": step_id,
            "goal": goal,
            "depends": depends,
            "status": "pending",
            "result": "",
        })
    return steps[:MAX_STEPS]


def parse_tool_commands(text: str) -> list[dict]:
    """Parse explicit tool commands into steps.

    Handles input like:
        run_search should_reflect app/chat.py
        run_read app/chat.py
        write_file app/chat.py <content>

    Each line becomes one step.
    """
    steps: list[dict] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        step_id = f"s{len(steps) + 1}"
        depends = [f"s{len(steps)}"] if steps else []
        steps.append({
            "id": step_id,
            "goal": line,
            "depends": depends,
            "status": "pending",
            "result": "",
        })
    return steps[:MAX_STEPS]


# ── Cleanup ───────────────────────────────────────────────────────


def clear() -> None:
    """Remove the buffer file."""
    try:
        if BUFFER_PATH.exists():
            os.remove(BUFFER_PATH)
    except OSError:
        pass


# ── Internal ──────────────────────────────────────────────────────


def _update_status(step_id: str, status: str, result: str) -> None:
    """Update a step's status and result. Atomic rewrite."""
    steps = read_all()
    for step in steps:
        if step["id"] == step_id:
            step["status"] = status
            step["result"] = result
            step["ts"] = time.time()
            break
    # Atomic rewrite with fsync for FAT32 safety
    _ensure_dir()
    tmp = str(BUFFER_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for step in steps:
            f.write(json.dumps(step, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, str(BUFFER_PATH))

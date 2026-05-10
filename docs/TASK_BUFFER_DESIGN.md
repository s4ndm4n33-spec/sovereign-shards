# Task Buffer Design — File-Based Planner/Executor Queue

> **Status:** Design doc (not yet implemented)
> **Target:** Phase 2, after endurance test passes
> **Principle:** Keep the queue *outside* the context window

---

## Problem

J runs on a 2048-token context window. Multi-step tasks (3+ steps) fail because:

1. The plan itself consumes ~100-200 tokens of context
2. Tool results from early steps push late steps out of context
3. J "forgets" what step it's on and either repeats or skips

The `/plan` command and the LLM-based planner (`app/agent/planner.py`) exist but are heavyweight — they require a full planning inference pass and use dataclasses that stay in memory.

## Solution: File-Based Task Buffer

A simple `.jsonl` file on disk that acts as a FIFO queue. The planner writes steps, the executor pops and runs them one at a time. The buffer lives *outside context*, so J's 2048 tokens are spent on the current step only.

```
memory/task_buffer.jsonl    ← the queue file
```

### Entry format

```json
{"id": "s1", "goal": "Read app/router.py to understand current routing", "status": "pending", "result": ""}
{"id": "s2", "goal": "Add regex for /model command", "status": "pending", "result": "", "depends": ["s1"]}
{"id": "s3", "goal": "Test the new route with a sample input", "status": "pending", "result": "", "depends": ["s2"]}
```

### Lifecycle

```
User: "add a /model command to the router"
           │
           ▼
    ┌─────────────┐
    │  PLAN MODE   │  Router detects multi-step → sets mode_hint="plan"
    │  (1 inference)│  Chat loop prepends [PLAN MODE] prefix
    └──────┬──────┘
           │ J outputs numbered steps
           ▼
    ┌──────────────┐
    │ BUFFER WRITE  │  Parse J's numbered steps → write to task_buffer.jsonl
    │ (0 inference) │  Each step = 1 line, status="pending"
    └──────┬──────┘
           │
           ▼
    ┌──────────────┐
    │ EXECUTE LOOP  │  For each pending step:
    │               │    1. Read step from file (pop)
    │               │    2. Inject as [CURRENT STEP] prompt
    │               │    3. Run 1-2 tool calls (budget from step complexity)
    │               │    4. Write result back to buffer line
    │               │    5. Update status → "done" or "failed"
    └──────┬──────┘
           │
           ▼
    ┌──────────────┐
    │ SUMMARY       │  Read completed steps from buffer
    │ (1 inference) │  Generate final response to user
    └──────────────┘
```

### Context Usage Per Phase

| Phase | Context consumed | Notes |
|-------|-----------------|-------|
| Plan | ~300 tokens | System prompt + user message + plan prefix |
| Execute (per step) | ~400 tokens | System prompt + step goal + tool result |
| Summary | ~500 tokens | System prompt + step summaries + user message |

Compare to current: all steps + all tool results in context simultaneously = context overflow by step 3.

## Implementation Spec

### `app/agent/task_buffer.py` — new file (~80 lines)

```python
"""File-based task buffer for plan/execute mode.

Steps are stored as JSONL on disk, outside the context window.
"""

from pathlib import Path
import json
import os

BUFFER_PATH = Path(__file__).parent.parent.parent / "memory" / "task_buffer.jsonl"

def write_plan(steps: list[dict]) -> None:
    """Write a fresh plan to the buffer. Overwrites any existing plan."""
    BUFFER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BUFFER_PATH, "w", encoding="utf-8") as f:
        for step in steps:
            step.setdefault("status", "pending")
            step.setdefault("result", "")
            f.write(json.dumps(step, ensure_ascii=False) + "\n")

def next_step() -> dict | None:
    """Return the next pending step, or None if done."""
    steps = _read_all()
    for step in steps:
        if step["status"] == "pending":
            # Check dependencies
            done_ids = {s["id"] for s in steps if s["status"] == "done"}
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

def summary() -> str:
    """Return a compact summary of all steps and their results."""
    steps = _read_all()
    lines = []
    for s in steps:
        icon = "✓" if s["status"] == "done" else "✗" if s["status"] == "failed" else "…"
        lines.append(f"{icon} {s['id']}: {s['goal']}")
        if s.get("result"):
            lines.append(f"  → {s['result'][:150]}")
    return "\n".join(lines)

def clear() -> None:
    """Remove the buffer file."""
    if BUFFER_PATH.exists():
        os.remove(BUFFER_PATH)

def _read_all() -> list[dict]:
    if not BUFFER_PATH.exists():
        return []
    entries = []
    with open(BUFFER_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries

def _update_status(step_id: str, status: str, result: str) -> None:
    steps = _read_all()
    for step in steps:
        if step["id"] == step_id:
            step["status"] = status
            step["result"] = result
            break
    # Atomic rewrite
    tmp = str(BUFFER_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for step in steps:
            f.write(json.dumps(step, ensure_ascii=False) + "\n")
    os.replace(tmp, str(BUFFER_PATH))
```

### Integration Points

1. **In `chat.py`:** After J responds in plan mode, parse the numbered steps and call `task_buffer.write_plan(steps)`
2. **Executor loop:** Replace the in-context plan with a file-read loop:
   - `step = task_buffer.next_step()`
   - Build focused step prompt (just system + current step)
   - Run 1-2 tool calls
   - `task_buffer.mark_done(step.id, result)`
3. **Summary phase:** After all steps done, inject `task_buffer.summary()` into context and ask J to summarize

### Parsing Numbered Steps from LLM Output

```python
import re

def parse_numbered_plan(text: str) -> list[dict]:
    """Extract numbered steps from J's plan output.
    
    Handles formats like:
    1. Read the router code
    2. Add the new route
    3. Test it
    """
    steps = []
    for match in re.finditer(r"^\d+\.\s*(.+)$", text, re.MULTILINE):
        step_id = f"s{len(steps) + 1}"
        goal = match.group(1).strip()
        depends = [f"s{len(steps)}"] if steps else []
        steps.append({"id": step_id, "goal": goal, "depends": depends})
    return steps
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| JSONL not JSON | Append-safe, atomic line writes, FAT32 friendly |
| File on disk, not in memory | Survives context trimming, no token cost while idle |
| Simple FIFO with depends | DAG is overkill for 7B model — sequential with optional skip |
| Atomic rewrite via .tmp + os.replace | USB-safe, no partial writes |
| Max 10 steps per plan | 7B models produce garbage beyond ~10 steps |
| Step results capped at 150 chars in summary | Keep final summary within context budget |

## What This Doesn't Solve

- **Parallel step execution** — not needed yet, 7B runs one inference at a time
- **Step retry logic** — failed step stops the plan (by design: user decides next move)
- **Cross-plan memory** — each plan is independent; working memory handles persistence

## Dependencies

- Requires plan/execute prompt templates (already built in this PR)
- Requires router `mode_hint` detection (already built in this PR)
- Does NOT require fine-tuning or additional model capabilities

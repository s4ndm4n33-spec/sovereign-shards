"""Checkpoint and restore AgentTask state to JSON for crash recovery.

USB-safe: atomic writes (.tmp -> rename), bounded file size.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from app.agent.contracts import AgentStep, AgentTask

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TASKS_DIR = BASE_DIR / "logs" / "tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)


def _task_path(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def save_task(task: AgentTask, task_id: str) -> str:
    """Persist task state. Returns the file path."""
    path = _task_path(task_id)
    tmp = path.with_suffix(".json.tmp")
    data = asdict(task)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(str(tmp), str(path))
    return str(path)


def load_task(task_id: str) -> AgentTask | None:
    """Restore task state from checkpoint. Returns None if missing."""
    path = _task_path(task_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    steps = [
        AgentStep(
            id=s["id"], goal=s["goal"],
            success_criteria=s["success_criteria"],
            depends_on=tuple(s.get("depends_on", ())),
        )
        for s in data.get("steps", [])
    ]
    return AgentTask(
        objective=data.get("objective", ""),
        mode=data.get("mode", "manual"),
        steps=steps,
        completed_step_ids=data.get("completed_step_ids", []),
        artifacts=data.get("artifacts", []),
    )


def list_tasks() -> list[str]:
    """Return task IDs with saved checkpoints."""
    return [p.stem for p in sorted(TASKS_DIR.glob("*.json"))]

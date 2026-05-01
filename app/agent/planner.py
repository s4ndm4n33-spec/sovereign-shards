"""Sovereign Planner: Strategic decomposition of goals into executable tasks.

Responsibilities:
  - Convert goals into AgentTasks with steps
  - Maintain task history and checkpoints
  - Support recovery from power loss (USB-first design)
"""
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from app.agent.contracts import AgentTask, TaskStatus


class SovereignPlanner:
    """Strategic brain of the Shard.
    
    Decomposes goals into verifiable, executable steps for the Kingston 2.0
    runtime. Supports USB-first persistence for power-loss resilience.
    """

    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent.parent
        self.task_history_dir = self.root / "logs" / "tasks"
        self.task_history_dir.mkdir(parents=True, exist_ok=True)

    def create_plan(self, goal: str, context: Dict[str, Any] = None) -> AgentTask:
        """Create a new task plan from a goal.
        
        Args:
            goal: The user's high-level goal/request
            context: Optional context dict (e.g., {"priority": "high"})
        
        Returns:
            AgentTask with empty steps (to be filled by router/planner)
        """
        # Generate unique task ID based on timestamp
        task_id = f"task_{int(time.time() * 1000)}"

        plan = AgentTask(
            task_id=task_id,
            goal=goal,
            steps=[],
            status="pending",
            checkpoint_file=str(self.task_history_dir / f"{task_id}.json")
        )

        # Persist immediately (checkpoint-first)
        self.save_checkpoint(plan)
        return plan

    def inject_steps(self, task: AgentTask, steps: List[Dict[str, Any]]) -> AgentTask:
        """Add steps to an existing task.
        
        Args:
            task: The AgentTask to modify
            steps: List of {"tool": name, "args": {...}} dicts
        
        Returns:
            Updated AgentTask
        """
        task.steps.extend(steps)
        task.status = "planning"
        self.save_checkpoint(task)
        return task

    def save_checkpoint(self, task: AgentTask) -> None:
        """Persist task state to disk for recovery.
        
        Uses FAT32-safe fsync to ensure writes survive power loss.
        Called after every state change.
        
        Args:
            task: The AgentTask to checkpoint
        """
        if not task.checkpoint_file:
            return

        try:
            with open(task.checkpoint_file, "w") as f:
                json.dump(task.to_dict(), f, indent=2)
                # Physical sync for FAT32 stability
                f.flush()
                try:
                    import os
                    os.fsync(f.fileno())
                except (OSError, AttributeError):
                    pass  # fsync not supported on all platforms
        except Exception as e:
            print(f"[WARN] Checkpoint failed for {task.task_id}: {str(e)}")

    def load_checkpoint(self, checkpoint_path: str) -> Optional[AgentTask]:
        """Load a task from checkpoint file.
        
        Args:
            checkpoint_path: Path to the checkpoint JSON file
        
        Returns:
            AgentTask if found, None otherwise
        """
        try:
            path = Path(checkpoint_path)
            if not path.exists():
                return None

            with open(path, "r") as f:
                data = json.load(f)
                return AgentTask(
                    task_id=data["task_id"],
                    goal=data["goal"],
                    steps=data["steps"],
                    status=data.get("status", "pending"),
                    checkpoint_file=data.get("checkpoint_file"),
                    created_at=data.get("created_at"),
                    completed_at=data.get("completed_at"),
                )
        except Exception as e:
            print(f"[ERROR] Failed to load checkpoint {checkpoint_path}: {str(e)}")
            return None

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all task checkpoints.
        
        Returns:
            List of {task_id, goal, status, created_at} dicts
        """
        tasks = []
        for checkpoint_file in self.task_history_dir.glob("task_*.json"):
            task = self.load_checkpoint(str(checkpoint_file))
            if task:
                tasks.append({
                    "task_id": task.task_id,
                    "goal": task.goal,
                    "status": task.status,
                    "created_at": task.created_at,
                })
        return sorted(tasks, key=lambda t: t["created_at"], reverse=True)

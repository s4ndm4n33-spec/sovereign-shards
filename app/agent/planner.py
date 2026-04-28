import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from app.agent.contracts import AgentTask

# // SEAM_START: PLANNER_CORE //

class SovereignPlanner:
    """
    The Strategic Brain of the Shard. 
    Decomposes goals into verifiable steps for the Kingston 2.0 runtime.
    """
    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent.parent
        self.task_history_dir = self.root / "logs" / "tasks"
        self.task_history_dir.mkdir(parents=True, exist_ok=True)

    def create_plan(self, goal: str, context: Dict[str, Any] = None) -> AgentTask:
        """
        In a full implementation, this calls the LLM to generate the step list.
        For now, it initializes the task structure for Governing Execution.
        """
        task_id = f"task_{int(Path('/dev/urandom').stat().st_mtime if Path('/dev/urandom').exists() else 0)}"
        
        # Placeholder for LLM-derived steps; currently structured for manual/semi-auto injection
        plan = AgentTask(
            task_id=task_id,
            goal=goal,
            steps=[],
            status="pending",
            checkpoint_file=str(self.task_history_dir / f"{task_id}.json")
        )
        return plan

    def save_checkpoint(self, task: AgentTask):
        """Persists the task state to the USB to survive power loss."""
        if task.checkpoint_file:
            with open(task.checkpoint_file, 'w') as f:
                json.dump(asdict(task), f, indent=4)
            # Physical Sync for FAT32 stability
            import os
            try:
                os.fsync(f.fileno())
            except:
                pass

# // SEAM_END: PLANNER_CORE //

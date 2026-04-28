from app.agent.scaffold import ToolRegistry
from app.agent.executor import HamiltonExecutor, AgentTask
from app.agent.planner import SovereignPlanner

registry = ToolRegistry()
planner = SovereignPlanner()
executor = HamiltonExecutor(registry)

task = planner.create_plan("Heartbeat Test")
task.steps = [
    {"tool": "exec", "args": {"command": "mkdir -p test_sequence"}},
    {"tool": "write", "args": {"path": "test_sequence/heartbeat.txt", "content": "STATUS: VERIFIED"}}
]

print(f"--- STARTING TASK: {task.task_id} ---")
for i in range(len(task.steps)):
    result = executor.execute_step(task, i)
    print(f"Step {i} Result: Success={result.success}")

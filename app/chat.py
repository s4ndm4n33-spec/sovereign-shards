from __future__ import annotations
import re
import sys
import json
from dataclasses import dataclass
from .agent.scaffold import build_default_registry
from .agent.executor import HamiltonExecutor
from .agent.planner import SovereignPlanner

@dataclass
class ChatSession:
    model: str
    system_prompt: str
    
    def __post_init__(self):
        self.registry = build_default_registry()
        self.executor = HamiltonExecutor(self.registry)
        self.planner = SovereignPlanner()

    def _run_turn(self, user_input: str) -> str:
    def _run_turn(self, user_input: str) -> str:
        raw_cmd = user_input.strip()
        cmd_lower = raw_cmd.lower()
        task = self.planner.create_plan(goal=user_input)
        
        if any(cmd_lower.startswith(x) for x in ['run ', 'execute ', 'bash ']):
            core_command = raw_cmd.split(' ', 1)[1]
            task.steps.append({'tool': 'exec', 'args': {'command': ['--command', core_command]}})
        elif 'read ' in cmd_lower:
            path = raw_cmd.split('read ', 1)[1].strip()
            task.steps.append({'tool': 'read', 'args': {'path': path}})
        
        if not task.steps:
            if 'status' in cmd_lower:
                from app.system_tools import get_system_snapshot
                return f'System Snapshot: {get_system_snapshot()}'
            return f'Intent logged: "{user_input}". No tool-chain mapped.'
                # 2. EXECUTION & LOUD OBSERVATION
        results = []
        for i in range(len(task.steps)):
            result = self.executor.execute_step(task, i)
            
            # The "Loud" Logic: capture EVERYTHING
            output_text = result.output.strip() if result.output else "PROCESS EXITED WITH NO DATA"
            status_icon = "✓" if result.success else "✗"
            
            formatted_res = (
                f"\n--- TOOL: {task.steps[i]['tool'].upper()} {status_icon} ---\n"
                f"{output_text}\n"
                f"----------------------------"
            )
            results.append(formatted_res)
        
        return "\n".join(results)

def run_chat():
    from app.controller import JarvisOneForAll
    boss = JarvisOneForAll()
    session = ChatSession(model="J.gguf", system_prompt=boss.get_system_header())
    print(f"\n[B.L.U.E.-J.] Logic: Stabilized. All systems wired.")
    
    while True:
        try:
            print("\n[USER]: ", end="", flush=True)
            user_msg = sys.stdin.readline()
            if not user_msg: break
            msg = user_msg.strip()
            if not msg: continue
            if msg.lower() in ["exit", "quit"]: break
            print(f"\n[B.L.U.E.-J.]: {session._run_turn(msg)}")
        except KeyboardInterrupt:
            break

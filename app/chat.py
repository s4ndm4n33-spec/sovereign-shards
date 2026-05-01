"""Chat Orchestrator: 6-Stage Execution Pipeline

Flow:
  1. PARSE: Extract intent from user input
  2. ROUTE: Map intent to tool chain (verb matching)
  3. PLAN: Convert tool chain into AgentTask with steps
  4. EXECUTE: Run each step via HamiltonExecutor
  5. EVALUATE: Five Masters governance hook (stubbed)
  6. FORMAT: Structure output for user display
"""
from __future__ import annotations
import re
import sys
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

from .agent.scaffold import build_default_registry
from .agent.executor import HamiltonExecutor
from .agent.planner import SovereignPlanner
from .agent.contracts import AgentTask, ToolCall, ToolResult, ExecutionContext
from .system_tools import get_system_snapshot


class IntentType(Enum):
    """User intent classification."""
    EXECUTE = "execute"    # run, bash, execute <command>
    READ = "read"          # read <path>
    WRITE = "write"        # write <path> <content>
    STATUS = "status"      # status, snapshot, health
    HELP = "help"          # help, ?
    EXIT = "exit"          # exit, quit
    UNKNOWN = "unknown"    # unrecognized


@dataclass
class ChatSession:
    """Encapsulates chat state and orchestration."""
    model: str
    system_prompt: str
    registry: Any = field(default_factory=build_default_registry)
    executor: Optional[HamiltonExecutor] = None
    planner: Optional[SovereignPlanner] = None

    def __post_init__(self):
        """Initialize agent subsystems."""
        if self.executor is None:
            self.executor = HamiltonExecutor(self.registry)
        if self.planner is None:
            self.planner = SovereignPlanner()

    # === STAGE 1: PARSE ===
    def _parse_intent(self, user_input: str) -> tuple[IntentType, str]:
        """Extract intent type and core command from user input.
        
        Returns:
            (IntentType, core_command_string)
        """
        raw = user_input.strip()
        lower = raw.lower()

        if lower in ["exit", "quit", "q"]:
            return IntentType.EXIT, ""
        elif lower in ["help", "?", "h"]:
            return IntentType.HELP, ""
        elif any(lower.startswith(x) for x in ["status", "snapshot", "health", "check"]):
            return IntentType.STATUS, ""
        elif any(lower.startswith(x) for x in ["run ", "execute ", "bash ", "exec "]):
            core = raw.split(" ", 1)[1] if " " in raw else ""
            return IntentType.EXECUTE, core
        elif any(lower.startswith(x) for x in ["read ", "cat ", "show "]):
            path = raw.split(" ", 1)[1].strip() if " " in raw else ""
            return IntentType.READ, path
        elif any(lower.startswith(x) for x in ["write ", "save "]):
            content = raw.split(" ", 1)[1].strip() if " " in raw else ""
            return IntentType.WRITE, content
        else:
            return IntentType.UNKNOWN, raw

    # === STAGE 2: ROUTE ===
    def _route_to_tools(self, intent: IntentType, command: str) -> List[Dict[str, Any]]:
        """Map intent to tool chain.
        
        Returns:
            List of {"tool": name, "args": {...}} dicts
        """
        tools = []

        if intent == IntentType.EXECUTE:
            tools.append({"tool": "exec", "args": {"command": command}})
        elif intent == IntentType.READ:
            tools.append({"tool": "read", "args": {"path": command}})
        elif intent == IntentType.WRITE:
            # parse: "path:content" or just content → file
            if ":" in command:
                path, content = command.split(":", 1)
                tools.append({"tool": "write", "args": {"path": path.strip(), "content": content.strip()}})
            else:
                tools.append({"tool": "write", "args": {"path": "output.txt", "content": command}})
        elif intent == IntentType.STATUS:
            tools.append({"tool": "snapshot", "args": {}})
        elif intent == IntentType.HELP:
            tools.append({"tool": "help", "args": {}})

        return tools

    # === STAGE 3: PLAN ===
    def _create_plan(self, user_input: str, tool_chain: List[Dict[str, Any]]) -> AgentTask:
        """Convert tool chain into executable AgentTask."""
        task = self.planner.create_plan(goal=user_input)
        task.steps = tool_chain
        return task

    # === STAGE 4: EXECUTE ===
    def _execute_plan(self, task: AgentTask) -> List[ToolResult]:
        """Run all steps in the task."""
        results = []
        for i in range(len(task.steps)):
            result = self.executor.execute_step(task, i)
            results.append(result)
        return results

    # === STAGE 5: EVALUATE ===
    def _evaluate_results(self, results: List[ToolResult]) -> bool:
        """Hook for Five Masters evaluation (stubbed).
        
        In a full implementation, this would:
        - Check code quality (AST-based Five Masters)
        - Validate output format
        - Flag suspicious patterns
        
        For now: Always pass.
        """
        return True  # TODO: Integrate Five Masters

    # === STAGE 6: FORMAT ===
    def _format_output(self, results: List[ToolResult], intent: IntentType) -> str:
        """Format tool results for user display."""
        if not results:
            return "[No tools executed]"

        formatted = []
        for result in results:
            status_icon = "✓" if result.success else "✗"
            output_text = result.output.strip() if result.output else "(no output)"

            formatted.append(
                f"\n--- {result.call_id} {status_icon} ---\n{output_text}\n"
            )

        return "".join(formatted)

    # === PUBLIC RUN TURN ===
    def run_turn(self, user_input: str) -> str:
        """Execute one full chat turn: parse → route → plan → execute → evaluate → format."""
        # Stage 1: Parse
        intent, command = self._parse_intent(user_input)

        # Handle special cases
        if intent == IntentType.EXIT:
            return "[EXITING]"
        elif intent == IntentType.UNKNOWN:
            return f'[UNRECOGNIZED]: "{user_input}". Try: run, read, write, status, help, exit'

        # Stage 2: Route
        tool_chain = self._route_to_tools(intent, command)
        if not tool_chain:
            return "[NO TOOLS MAPPED]"

        # Stage 3: Plan
        task = self._create_plan(user_input, tool_chain)

        # Stage 4: Execute
        results = self._execute_plan(task)

        # Stage 5: Evaluate
        is_valid = self._evaluate_results(results)
        if not is_valid:
            return "[EVALUATION FAILED: Governance violation]"

        # Stage 6: Format
        return self._format_output(results, intent)


def run_chat():
    """Main chat loop: REPL for the Shard."""
    from app.controller import JarvisOneForAll

    boss = JarvisOneForAll()
    session = ChatSession(model="J.gguf", system_prompt=boss.get_system_header())
    print(f"\n[B.L.U.E.-J.] Logic: Stabilized. All systems wired.")
    print(f"[B.L.U.E.-J.] Type 'help' for commands, 'exit' to quit.\n")

    while True:
        try:
            print("[USER]: ", end="", flush=True)
            user_msg = sys.stdin.readline()
            if not user_msg:
                break

            msg = user_msg.strip()
            if not msg:
                continue

            if msg.lower() in ["exit", "quit", "q"]:
                break

            result = session.run_turn(msg)
            print(f"\n[B.L.U.E.-J.]: {result}\n")

        except KeyboardInterrupt:
            print("\n[INTERRUPTED]")
            break
        except Exception as e:
            print(f"\n[ERROR]: {str(e)}\n")

"""Enhanced Chat Orchestrator: 6-Stage Pipeline + LLM Integration

Flow:
  1. PARSE: Extract intent from user input
  2. ROUTE: Map intent to tool chain (verb matching)
  3. PLAN: Convert tool chain into AgentTask with steps
  4. EXECUTE: Run each step via HamiltonExecutor
  5. EVALUATE: Pass through Five Masters governance hook
  6. FORMAT: Structure output for user display

With LLM integration:
  - Tool output goes to model for reasoning
  - Model can generate followup tasks
  - Reasoning stored in task context
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
from .llm_client import LLMClient
from .client import create_client
from .controller import JarvisOneForAll


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
    """Encapsulates chat state and orchestration with LLM."""
    model: str
    system_prompt: str
    registry: Any = field(default_factory=build_default_registry)
    executor: Optional[HamiltonExecutor] = None
    planner: Optional[SovereignPlanner] = None
    llm_client: Optional[LLMClient] = None
    reasoning_enabled: bool = True

    def __post_init__(self):
        """Initialize agent subsystems."""
        if self.executor is None:
            self.executor = HamiltonExecutor(self.registry)
        if self.planner is None:
            self.planner = SovereignPlanner()
        if self.llm_client is None:
            try:
                config = create_client()
                self.llm_client = LLMClient(config)
            except Exception as e:
                print(f"[WARN] LLM init failed: {e}. Operating in tool-only mode.")
                self.llm_client = None
    
    
    def fast_route(self, user_input: str) -> Optional[tuple[IntentType, str]]:
        text = user_input.strip()
        lower = text.lower()

          # --- NORMALIZATION STEP --- #
        if (text.startswith("'") and text.endswith("'")) or (
            text.startswith('"') and text.endswith('"')):
            text = text[1:-1].strip()

            lower = text.lower() 
        
        if lower.startswith(("read ", "cat ", "show ")):
            path = text.split(" ", 1)[1].strip() if " " in text else ""
            return IntentType.READ, path

        if lower.startswith(("write ", "save ", "create ")):
            content = text.split(" ", 1)[1].strip() if " " in text else ""
            return IntentType.WRITE, content

        if lower in ["status", "snapshot", "health", "check"]:
            return IntentType.STATUS, ""

        if lower in ["help", "?", "h"]:
            return IntentType.HELP, ""

        if lower in ["exit", "quit", "q"]:
            return IntentType.EXIT, ""

        return None
    
     # === STAGE 1: PARSE ===
    def _parse_intent(self, user_input: str) -> tuple[IntentType, str]:
        """Extract intent type and core command from user input."""
        raw = user_input.strip()
        lower = raw.lower()

        if lower in ["exit", "quit", "q"]:
            return IntentType.EXIT, ""
        elif lower in ["help", "?", "h"]:
            return IntentType.HELP, ""
        elif any(lower.startswith(x) for x in ["status", "snapshot", "health", "check"]):
            return IntentType.STATUS, ""
        elif any(lower.startswith(x) for x in ["run ", "execute ", "bash ", "exec ", "cmd "]):
            core = raw.split(" ", 1)[1] if " " in raw else ""
            return IntentType.EXECUTE, core
        elif any(lower.startswith(x) for x in ["read ", "cat ", "show "]):
            path = raw.split(" ", 1)[1].strip() if " " in raw else ""
            return IntentType.READ, path
        elif any(lower.startswith(x) for x in ["write ", "save ", "create "]):
            content = raw.split(" ", 1)[1].strip() if " " in raw else ""
            return IntentType.WRITE, content
        else:
            return IntentType.UNKNOWN, raw

    # === STAGE 2: ROUTE ===
    def _route_to_tools(self, intent: IntentType, command: str) -> List[Dict[str, Any]]:
        """Map intent to tool chain."""
        tools = []

        if intent == IntentType.EXECUTE:
            if command.startswith("pip "):
                action = "install" if "install" in command else "uninstall"
                libs = command.replace("pip install ", "").replace("pip uninstall ", "").split()
                tools.append({"tool": "packager_tool", "args": {"libs": libs, "action": action}})
            elif command.startswith("sql:"):
                query = command.replace("sql:", "", 1).strip()
                tools.append({"tool": "execute_sql_tool", "args": {"sql_query": query}})
            else:
                tools.append({"tool": "bash", "args": {"command": command}})
        elif intent == IntentType.READ:
            tools.append({"tool": "read", "args": {"path": command}})
        elif intent == IntentType.WRITE:
            if ":" in command:
                path, content = command.split(":", 1)
                tools.append({"tool": "write", "args": {"path": path.strip(), "content": content.strip()}})
            else:
                tools.append({"tool": "write", "args": {"path": "output.txt", "content": command}})
        elif intent == IntentType.STATUS:
            tools.append({"tool": "sentry", "args": {}})
        elif intent == IntentType.HELP:
            tools.append({"tool": "suggest_deploy", "args": {}})

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
        """Hook for Five Masters evaluation (stubbed)."""
        return True  # TODO: Integrate Five Masters

    # === STAGE 6: FORMAT + LLM REASONING ===
    def _format_output(self, results: List[ToolResult], user_input: str, intent: IntentType) -> str:
        """Format results and optionally use LLM for reasoning."""
        if not results:
            return "[No tools executed]"

        # Collect raw output
        raw_output = "\n".join(
            f"[{r.call_id}] {'✓' if r.success else '✗'}\n{r.output}"
            for r in results
        )

        # If LLM available and reasoning enabled, ask for interpretation
        if self.llm_client and self.reasoning_enabled and intent in [
            IntentType.EXECUTE,
            IntentType.READ,
            IntentType.STATUS,
        ]:
            try:
                reasoning_prompt = f"""
User asked: {user_input}

Tool output:
{raw_output}

Briefly explain what this output means and if any action is needed.
Keep response under 100 words. Be direct and technical.
"""
                reasoning = self.llm_client.generate_text(
                    reasoning_prompt,
                    system=self.system_prompt,
                    max_tokens=150,
                )
                return f"{raw_output}\n\n[REASONING]\n{reasoning}"
            except Exception as e:
                # Fallback to raw output if LLM fails
                return raw_output
        else:
            return raw_output

    # === PUBLIC RUN TURN ===
    def run_turn(self, user_input: str) -> str:
        """Execute one full chat turn: parse → route → plan → execute → evaluate → format."""
        
        # --- FAST ROUTER --- #
        fast = self.fast_route(user_input)
      
        if fast:
            intent, command = fast
        else:
            # fallback to existing parser
            intent, command = self._parse_intent(user_input)

        # Handle special cases
        if intent == IntentType.EXIT:
            return "[EXITING]"
        elif intent == IntentType.UNKNOWN:
            # Try LLM for unknown intents
            if self.llm_client and self.reasoning_enabled:
                try:
                    response = self.llm_client.generate_text(
                        user_input,
                        system=self.system_prompt,
                        max_tokens=200,
                    )
                    return response
                except Exception:
                    pass
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

        # Stage 6: Format + Reasoning
        return self._format_output(results, user_input, intent)


def run_chat():
    """Main chat loop: REPL for the Shard with LLM support."""
    boss = JarvisOneForAll()
    config = None
    try:
        config = create_client()
    except Exception as e:
        print(f"[WARN] Config load failed: {e}")

    session = ChatSession(
        model="J.gguf",
        system_prompt=boss.get_system_header(),
    )

    print(f"\n[B.L.U.E.-J.] Logic: Stabilized. All systems wired.")
    if session.llm_client:
        print(f"[B.L.U.E.-J.] LLM: ACTIVE at {session.llm_client.base_url}")
    else:
        print(f"[B.L.U.E.-J.] LLM: OFFLINE (tool-only mode)")
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

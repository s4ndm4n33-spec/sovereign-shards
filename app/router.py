"""Fast deterministic command router — sits BEFORE the LLM.

Intercepts direct commands, shell invocations, and tool prefixes so the
language model only touches input that genuinely needs reasoning.
Zero inference cost for anything the router handles.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.tool_registry import ToolRegistry


@dataclass
class RouteResult:
    """Outcome of the fast router."""

    handled: bool            # True → router executed it, skip LLM
    tool_name: str = ""      # which tool was dispatched
    tool_args: list = None   # args passed
    output: str = ""         # tool output (if handled)
    tool_budget: int = 1     # max tool calls the LLM gets this turn
    mode_hint: str = ""      # "plan" → inject plan-mode prompt prefix

    def __post_init__(self):
        if self.tool_args is None:
            self.tool_args = []


# ── Pattern matchers ────────────────────────────────────────────────

# Obvious shell commands (prefixes that are unambiguous)
_SHELL_PREFIXES = (
    "python ", "python3 ", "pip ", "pip3 ",
    "git ", "ls ", "cat ", "cd ", "mkdir ", "rm ", "mv ", "cp ",
    "find ", "grep ", "head ", "tail ", "wc ", "chmod ", "touch ",
    "echo ", "pwd", "tree ", "which ", "curl ", "wget ",
    "npm ", "node ", "cargo ", "make ", "cmake ",
    "docker ", "pytest ", "bash ", "sh ",
)

# Explicit tool-call syntax: run_bash <cmd>, run_read <path>, etc.
_TOOL_PREFIX_RE = re.compile(r"^(run_\w+)\s*(.*)", re.DOTALL)

# Looks like a file path operation
_PATH_OP_RE = re.compile(
    r"^(read|write|cat|show|open|view|display)\s+([^\s]+\.\w+)",
    re.IGNORECASE,
)

# Inline code fence that should be executed: ```bash ... ```
_CODE_FENCE_RE = re.compile(
    r"^```(?:bash|sh|shell|python)?\s*\n(.+?)\n```$",
    re.DOTALL | re.IGNORECASE,
)


def route(user_input: str, registry: "ToolRegistry") -> RouteResult:
    """Attempt to deterministically route the input. Returns handled=False
    if the input needs the LLM."""

    stripped = user_input.strip()
    lowered = stripped.lower()

    # ── 1. Slash commands are handled elsewhere (return unhandled) ──
    if stripped.startswith("/"):
        return RouteResult(handled=False)

    # ── 2. Explicit run_* tool prefix ───────────────────────────────
    m = _TOOL_PREFIX_RE.match(stripped)
    if m:
        tool_name = m.group(1)
        rest = m.group(2).strip()
        if tool_name in registry.tools:
            args = _split_args(rest) if rest else []
            output = registry.execute(tool_name, args)
            return RouteResult(
                handled=True,
                tool_name=tool_name,
                tool_args=args,
                output=output,
            )

    # ── 3. Obvious shell commands → run_bash ────────────────────────
    if any(lowered.startswith(p) for p in _SHELL_PREFIXES) or lowered == "pwd":
        return _dispatch_bash(stripped, registry)

    # ── 4. Bare command with known executable pattern ───────────────
    #    e.g. "python -m unittest discover -s tests -v"
    if re.match(r"^[\w./-]+\s+-", stripped) and _looks_like_command(stripped):
        return _dispatch_bash(stripped, registry)

    # ── 5. Code fence with bash/python ──────────────────────────────
    m = _CODE_FENCE_RE.match(stripped)
    if m:
        return _dispatch_bash(m.group(1).strip(), registry)

    # ── 6. Path-based read: "read run.py", "cat app/chat.py" ───────
    m = _PATH_OP_RE.match(stripped)
    if m:
        verb = m.group(1).lower()
        path = m.group(2)
        if verb in ("read", "cat", "show", "open", "view", "display"):
            if "run_read" in registry.tools:
                output = registry.execute("run_read", [path])
                return RouteResult(handled=True, tool_name="run_read",
                                   tool_args=[path], output=output)
            elif "read_file" in registry.tools:
                output = registry.execute("read_file", [path])
                return RouteResult(handled=True, tool_name="read_file",
                                   tool_args=[path], output=output)

    # ── 7. No match → classify complexity and set tool budget ───────
    budget = _classify_budget(stripped, lowered)
    mode = _classify_mode(stripped, lowered)
    return RouteResult(handled=False, tool_budget=budget, mode_hint=mode)


# ── Budget classifier ───────────────────────────────────────────────

# Keywords that signal multi-step work (each match adds to budget)
_MULTI_STEP_KEYWORDS = (
    "then", "and then", "after that", "next", "also",
    "compare", "both", "each", "all",
    "update", "fix", "refactor", "change", "modify", "replace",
)

# Keywords that signal single-tool work (budget stays at 1)
_SINGLE_KEYWORDS = (
    "read", "show", "search", "find", "list", "what", "who",
    "explain", "tell me", "describe", "check",
)


def _classify_budget(text: str, lowered: str) -> int:
    """Estimate how many tool calls this prompt needs. Zero inference cost."""

    # Agent mode gets full budget
    if lowered.startswith("/plan"):
        return 5

    # Count multi-step signals
    multi_signals = sum(1 for kw in _MULTI_STEP_KEYWORDS if kw in lowered)

    # Count distinct tool-like verbs (read + search = 2 tools)
    tool_verbs = sum(1 for v in ("read", "search", "write", "run", "bash", "list", "tree")
                     if v in lowered)

    if multi_signals >= 2 or tool_verbs >= 3:
        return 3  # complex multi-step
    if multi_signals >= 1 or tool_verbs >= 2:
        return 2  # moderate
    return 1      # simple single-tool or conversational


def _classify_mode(text: str, lowered: str) -> str:
    """Detect if the prompt benefits from plan-before-act mode.

    Returns "plan" when the request has 2+ distinct steps or explicit
    planning language.  Returns "" for simple/single-step requests.
    Zero inference cost — pure keyword matching.
    """
    # Explicit planning language
    _PLAN_SIGNALS = (
        "step by step", "break it down", "walk me through",
        "plan", "first.*then", "compare.*and",
    )
    for signal in _PLAN_SIGNALS:
        if re.search(signal, lowered):
            return "plan"

    # Multi-verb detection: "read X and write Y", "search then fix"
    action_verbs = sum(1 for v in (
        "read", "search", "write", "create", "update", "fix",
        "delete", "move", "rename", "compare", "run", "test",
    ) if v in lowered)

    connectors = sum(1 for c in ("then", "and then", "after that", "next", "also", "and")
                     if c in lowered)

    if action_verbs >= 2 and connectors >= 1:
        return "plan"

    return ""


# ── Internal helpers ────────────────────────────────────────────────

def _dispatch_bash(command: str, registry: "ToolRegistry") -> RouteResult:
    """Route a shell command to the bash tool."""
    # Prefer run_bash, fall back to run_exec
    for tool in ("run_bash", "run_exec"):
        if tool in registry.tools:
            output = registry.execute(tool, [command])
            return RouteResult(
                handled=True, tool_name=tool,
                tool_args=[command], output=output,
            )
    # No bash tool available — can't handle
    return RouteResult(handled=False)


def _split_args(text: str) -> list[str]:
    """Shell-aware argument splitting."""
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _looks_like_command(text: str) -> bool:
    """Heuristic: does this look like a CLI invocation?"""
    first_word = text.split()[0] if text.split() else ""
    # Ends with known executable extension or is a known command pattern
    if "/" in first_word or first_word.endswith((".py", ".sh", ".bat", ".exe")):
        return True
    # Has flags (dashes)
    if " -" in text:
        return True
    return False

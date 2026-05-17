# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Fast deterministic command router — sits BEFORE the LLM.

Intercepts direct commands, shell invocations, tool prefixes, and
arithmetic so the language model only touches input that genuinely
needs reasoning. Zero inference cost for anything the router handles.
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

    def __post_init__(self):
        if self.tool_args is None:
            self.tool_args = []


# ── Pattern matchers ────────────────────────────────────────────────

# Obvious shell commands (prefixes that are unambiguous)
_SHELL_PREFIXES = (
    # Unix
    "python ", "python3 ", "pip ", "pip3 ",
    "git ", "ls ", "cat ", "cd ", "mkdir ", "rm ", "mv ", "cp ",
    "find ", "grep ", "head ", "tail ", "wc ", "chmod ", "touch ",
    "echo ", "tree ", "which ", "curl ", "wget ",
    "npm ", "node ", "cargo ", "make ", "cmake ",
    "docker ", "pytest ", "bash ", "sh ",
    # Windows
    "dir ", "type ", "del ", "copy ", "move ", "md ", "rd ",
    "cls", "ver",
)
# Bare commands (no args needed)
_BARE_SHELL = ("pwd", "dir", "cls", "ver")

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

# ── Math detection patterns ─────────────────────────────────────────
#
# Two tiers:
#   A) Direct arithmetic: "47 * 13", "100 + 200", "(3 + 4) * 5"
#   B) Natural language:  "what is 47 times 13?", "how much is 365 / 7"
#
# We check AFTER slash commands and tool prefixes so "run_calc ..."
# still works via rule 2, and "/plan calculate ..." hits the LLM.

# Direct arithmetic: contains digits + operators, optionally with
# math function names and parens. Must have at least one operator
# between two numbers to qualify.
_DIRECT_MATH_RE = re.compile(
    r"^[\d\s+\-*/%.()^,]+$"
)

# Natural language math triggers
_NL_MATH_RE = re.compile(
    r"(?:what\s+is|what\'s|calculate|compute|solve|evaluate|how\s+much\s+is)"
    r"\s+.*\d",
    re.IGNORECASE,
)

# Word-form operators that signal arithmetic intent
_WORD_MATH_RE = re.compile(
    r"\d+\s+(?:times|multiplied\s+by|divided\s+by|plus|minus|over"
    r"|mod|modulo|to\s+the\s+power\s+of|squared|cubed)\b",
    re.IGNORECASE,
)

# Math function calls: sqrt(144), log(100), etc.
_FUNC_MATH_RE = re.compile(
    r"^(?:sqrt|abs|round|min|max|pow|log|log2|log10|sin|cos|tan"
    r"|ceil|floor|factorial)\s*\(",
    re.IGNORECASE,
)


def _is_math(stripped: str, lowered: str) -> bool:
    """Return True if the input looks like a math question."""
    # Direct arithmetic: "47 * 13", "(3+4)*5"
    # Must have at least one operator and one digit
    if _DIRECT_MATH_RE.match(stripped):
        has_digit = any(c.isdigit() for c in stripped)
        has_op = any(c in stripped for c in "+-*/%")
        if has_digit and has_op:
            return True

    # Natural language: "what is 47 times 13?"
    if _NL_MATH_RE.search(lowered):
        return True

    # Word operators: "47 times 13", "100 divided by 7"
    if _WORD_MATH_RE.search(stripped):
        return True

    # Math function: "sqrt(144)", "round(22/7, 4)"
    if _FUNC_MATH_RE.match(stripped):
        return True

    return False


def route(user_input: str, registry: "ToolRegistry") -> RouteResult:
    """Attempt to deterministically route the input. Returns handled=False
    if the input needs the LLM."""

    stripped = user_input.strip()
    # Strip surrounding quotes — user often wraps input in "..." or '...'
    # which silently breaks every regex pattern in this router.
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ('"', "'"):
        stripped = stripped[1:-1].strip()
    lowered = stripped.lower()

    # ── 1. Slash commands are handled elsewhere (return unhandled) ──
    if stripped.startswith("/"):
        return RouteResult(handled=False)

    # ── 2. Explicit tool name prefix (run_read, write_file, etc.) ───
    # Match ANY registered tool name, not just run_* prefixes.
    first_word = stripped.split()[0] if stripped.split() else ""
    if first_word in registry.tools:
        rest = stripped[len(first_word):].strip()
        # Tools whose first arg is piped to stdin need the WHOLE rest
        # string as one arg — don't shlex-split shell commands.
        _STDIN_TOOLS = ("run_bash", "run_exec")
        if first_word in _STDIN_TOOLS:
            args = [rest] if rest else []
        else:
            args = _split_args(rest) if rest else []
        # Default path for list_dir when no args given
        if first_word == "list_dir" and not args:
            args = ["."]
        output = registry.execute(first_word, args)
        return RouteResult(
            handled=True,
            tool_name=first_word,
            tool_args=args,
            output=output,
        )

    # ── 3. Obvious shell commands → run_bash ────────────────────────
    if any(lowered.startswith(p) for p in _SHELL_PREFIXES) or lowered in _BARE_SHELL:
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

    # ── 7. Arithmetic → run_calc (zero inference cost) ──────────────
    if "run_calc" in registry.tools and _is_math(stripped, lowered):
        output = registry.execute("run_calc", [stripped])
        return RouteResult(
            handled=True,
            tool_name="run_calc",
            tool_args=[stripped],
            output=output,
        )

    # ── 8. No match → classify complexity and set tool budget ───────
    budget = _classify_budget(stripped, lowered)
    return RouteResult(handled=False, tool_budget=budget)


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
    """Estimate how many tool calls this prompt needs. Zero inference cost.

    Returns 0 for pure chat (identity, math, general knowledge) so the
    tool loop accepts J's answer without forcing a tool call.

    Budget tiers:
        0  — pure chat, no tools needed
        1  — one-shot tool call
        2  — moderate (two tools or one multi-step keyword)
        3  — complex multi-step
        25 — heavy pipeline (many explicit steps)
    """

    # Agent mode gets full budget
    if lowered.startswith("/plan"):
        return 25

    # Count distinct tool-like verbs (read + search = 2 tools)
    tool_verbs = sum(1 for v in ("read", "search", "write", "run", "bash", "list", "tree")
                     if v in lowered)

    # No tool verbs → pure chat/knowledge question → budget 0
    if tool_verbs == 0:
        return 0

    # Count multi-step signals
    multi_signals = sum(1 for kw in _MULTI_STEP_KEYWORDS if kw in lowered)

    # Count explicit "then" occurrences (each is a distinct sequential step)
    then_count = lowered.count("then ")

    # Heavy pipeline: many sequential steps with multiple tool types
    # e.g. "run_tree ... then run_read each ... then run_write ... then run_read"
    if then_count >= 3 or (tool_verbs >= 3 and multi_signals >= 3):
        return 25  # enough room for 17-file sweeps etc.

    if multi_signals >= 2 or tool_verbs >= 3:
        return 3  # complex multi-step
    if multi_signals >= 1 or tool_verbs >= 2:
        return 2  # moderate
    return 1      # simple single-tool


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
    """Shell-aware argument splitting.

    Normalises Windows backslashes to forward slashes before splitting
    so shlex doesn't eat them as escape sequences (e.g. prompts\\J-system.txt
    → prompts/J-system.txt). Python's open() handles forward slashes on
    Windows, so this is safe for all file-based tools.
    """
    # Replace backslashes with forward slashes to survive shlex posix mode.
    # This is safe because tool args are file paths or content strings —
    # neither needs literal backslashes.
    normalized = text.replace("\\", "/")
    try:
        return shlex.split(normalized)
    except ValueError:
        return normalized.split()


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

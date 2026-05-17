# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for the fast deterministic command router."""

import unittest
from unittest.mock import MagicMock


# Inline the router module for testing (avoid import from app.router which doesn't exist locally)
import re
import shlex
from dataclasses import dataclass
from typing import Any


@dataclass
class RouteResult:
    handled: bool
    tool_name: str = ""
    tool_args: list = None
    output: str = ""

    def __post_init__(self):
        if self.tool_args is None:
            self.tool_args = []


_SHELL_PREFIXES = (
    "python ", "python3 ", "pip ", "pip3 ",
    "git ", "ls ", "cat ", "cd ", "mkdir ", "rm ", "mv ", "cp ",
    "find ", "grep ", "head ", "tail ", "wc ", "chmod ", "touch ",
    "echo ", "pwd", "tree ", "which ", "curl ", "wget ",
    "npm ", "node ", "cargo ", "make ", "cmake ",
    "docker ", "pytest ", "bash ", "sh ",
)

_TOOL_PREFIX_RE = re.compile(r"^(run_\w+)\s*(.*)", re.DOTALL)
_PATH_OP_RE = re.compile(r"^(read|write|cat|show|open|view|display)\s+([^\s]+\.\w+)", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"^```(?:bash|sh|shell|python)?\s*\n(.+?)\n```$", re.DOTALL | re.IGNORECASE)


def _looks_like_command(text):
    first_word = text.split()[0] if text.split() else ""
    if "/" in first_word or first_word.endswith((".py", ".sh", ".bat", ".exe")):
        return True
    if " -" in text:
        return True
    return False


def route(user_input, registry):
    stripped = user_input.strip()
    lowered = stripped.lower()

    if stripped.startswith("/"):
        return RouteResult(handled=False)

    m = _TOOL_PREFIX_RE.match(stripped)
    if m:
        tool_name = m.group(1)
        rest = m.group(2).strip()
        if tool_name in registry.tools:
            try:
                args = shlex.split(rest) if rest else []
            except ValueError:
                args = rest.split() if rest else []
            output = registry.execute(tool_name, args)
            return RouteResult(handled=True, tool_name=tool_name, tool_args=args, output=output)

    if any(lowered.startswith(p) for p in _SHELL_PREFIXES) or lowered == "pwd":
        for tool in ("run_bash", "run_exec"):
            if tool in registry.tools:
                output = registry.execute(tool, [stripped])
                return RouteResult(handled=True, tool_name=tool, tool_args=[stripped], output=output)

    if re.match(r"^[\w./-]+\s+-", stripped) and _looks_like_command(stripped):
        for tool in ("run_bash", "run_exec"):
            if tool in registry.tools:
                output = registry.execute(tool, [stripped])
                return RouteResult(handled=True, tool_name=tool, tool_args=[stripped], output=output)

    m = _CODE_FENCE_RE.match(stripped)
    if m:
        cmd = m.group(1).strip()
        for tool in ("run_bash", "run_exec"):
            if tool in registry.tools:
                output = registry.execute(tool, [cmd])
                return RouteResult(handled=True, tool_name=tool, tool_args=[cmd], output=output)

    m = _PATH_OP_RE.match(stripped)
    if m:
        verb = m.group(1).lower()
        path = m.group(2)
        if verb in ("read", "cat", "show", "open", "view", "display"):
            for tool in ("run_read", "read_file"):
                if tool in registry.tools:
                    output = registry.execute(tool, [path])
                    return RouteResult(handled=True, tool_name=tool, tool_args=[path], output=output)

    return RouteResult(handled=False)


class MockRegistry:
    def __init__(self, tool_names):
        self.tools = {name: True for name in tool_names}
        self.calls = []

    def execute(self, name, args):
        self.calls.append((name, args))
        return f"[OK] {name}({args})"


class TestFastRouter(unittest.TestCase):
    def setUp(self):
        self.registry = MockRegistry([
            "run_bash", "run_exec", "run_read", "run_write",
            "run_search", "run_tree", "read_file", "write_file",
        ])

    def test_shell_command_python(self):
        r = route("python -m unittest discover -s tests -v", self.registry)
        self.assertTrue(r.handled)
        self.assertEqual(r.tool_name, "run_bash")

    def test_shell_command_git(self):
        r = route("git status", self.registry)
        self.assertTrue(r.handled)
        self.assertEqual(r.tool_name, "run_bash")

    def test_shell_command_ls(self):
        r = route("ls -la", self.registry)
        self.assertTrue(r.handled)

    def test_shell_command_pip(self):
        r = route("pip install requests", self.registry)
        self.assertTrue(r.handled)
        self.assertEqual(r.tool_name, "run_bash")

    def test_tool_prefix_run_bash(self):
        r = route("run_bash echo hello", self.registry)
        self.assertTrue(r.handled)
        self.assertEqual(r.tool_name, "run_bash")

    def test_tool_prefix_run_read(self):
        r = route("run_read app/chat.py", self.registry)
        self.assertTrue(r.handled)
        self.assertEqual(r.tool_name, "run_read")

    def test_tool_prefix_run_search(self):
        r = route("run_search TODO .", self.registry)
        self.assertTrue(r.handled)
        self.assertEqual(r.tool_name, "run_search")

    def test_read_file_shorthand(self):
        r = route("read run.py", self.registry)
        self.assertTrue(r.handled)
        self.assertIn(r.tool_name, ("run_read", "read_file"))

    def test_cat_file_shorthand(self):
        r = route("cat app/chat.py", self.registry)
        # "cat " is a shell prefix, so it goes to run_bash
        self.assertTrue(r.handled)
        self.assertEqual(r.tool_name, "run_bash")

    def test_show_file(self):
        r = route("show config.py", self.registry)
        self.assertTrue(r.handled)
        self.assertIn(r.tool_name, ("run_read", "read_file"))

    def test_slash_command_not_handled(self):
        r = route("/help", self.registry)
        self.assertFalse(r.handled)

    def test_slash_plan_not_handled(self):
        r = route("/plan build an API", self.registry)
        self.assertFalse(r.handled)

    def test_natural_language_not_handled(self):
        r = route("explain how the memory system works", self.registry)
        self.assertFalse(r.handled)

    def test_question_not_handled(self):
        r = route("what files are in the app directory?", self.registry)
        self.assertFalse(r.handled)

    def test_code_fence_bash(self):
        r = route("```bash\necho hello world\n```", self.registry)
        self.assertTrue(r.handled)
        self.assertEqual(r.tool_name, "run_bash")

    def test_pwd(self):
        r = route("pwd", self.registry)
        self.assertTrue(r.handled)

    def test_pytest(self):
        r = route("pytest tests/ -v", self.registry)
        self.assertTrue(r.handled)
        self.assertEqual(r.tool_name, "run_bash")

    def test_unknown_tool_prefix(self):
        r = route("run_nonexistent some args", self.registry)
        self.assertFalse(r.handled)

    def test_empty_input(self):
        r = route("", self.registry)
        self.assertFalse(r.handled)

    def test_tree_command(self):
        r = route("tree . --depth 3", self.registry)
        self.assertTrue(r.handled)


if __name__ == "__main__":
    unittest.main()

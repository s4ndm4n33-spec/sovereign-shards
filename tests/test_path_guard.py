# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Path-sanity guards reject prompt-as-path inputs at both enforcement points.

Regression test for the failure where the agent passed an entire task
description as a path argument, and mkdir(parents=True) exploded the
embedded slashes into a tree of nested junk directories.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "run"))

from app.file_tools import _pathological_reason, _resolve, write_file  # noqa: E402
import _path_guard  # noqa: E402

# The real input that created the junk directory tree under docs/.
PROMPT_PATH = (
    "docs/TOOL_REFERENCE.md - run_tree tools/run to list all 17 script tools, "
    "then run_read each .py file to extract name, description, args, side_effect, "
    "and timeout, then run_read app/router.py for the fast-route regex patterns, "
    "then run_write the doc with a quick-reference table and per-tool sections"
)


class PathologicalReason(unittest.TestCase):
    def test_prompt_path_rejected(self):
        self.assertIsNotNone(_pathological_reason(PROMPT_PATH))

    def test_newline_rejected(self):
        self.assertIsNotNone(_pathological_reason("docs/foo\nbar.md"))

    def test_overlong_component_rejected(self):
        self.assertIsNotNone(_pathological_reason("docs/" + "x" * 200 + ".md"))

    def test_normal_paths_accepted(self):
        for ok in ("app/chat.py", "docs/TOOL_REFERENCE.md", "tools/run/write.py", "."):
            self.assertIsNone(_pathological_reason(ok), ok)


class ResolveGuard(unittest.TestCase):
    def test_resolve_raises_on_prompt_path(self):
        with self.assertRaises(ValueError):
            _resolve(PROMPT_PATH)

    def test_resolve_ok_on_normal(self):
        _resolve("app/chat.py")  # must not raise


class WriteFileGuard(unittest.TestCase):
    def test_write_rejects_and_creates_nothing(self):
        docs = ROOT / "docs"
        before = {p.name for p in docs.iterdir()}
        with self.assertRaises(ValueError):
            write_file(PROMPT_PATH, "junk")
        after = {p.name for p in docs.iterdir()}
        self.assertEqual(before, after, "guard must not create any directories")


class SafePathGuard(unittest.TestCase):
    def test_safe_path_exits_on_prompt_path(self):
        with self.assertRaises(SystemExit):
            _path_guard.safe_path(PROMPT_PATH, allow_create=True)

    def test_safe_path_ok_on_existing(self):
        resolved = _path_guard.safe_path("app/chat.py")
        self.assertTrue(str(resolved).endswith("chat.py"))


if __name__ == "__main__":
    unittest.main()

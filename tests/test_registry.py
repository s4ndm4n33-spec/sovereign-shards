# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for tool registry (app.agent.tool_registry)."""

import os
import tempfile
import unittest
from pathlib import Path

from app.agent.tool_registry import ToolRegistry, ToolSpec, ScriptTool


class TestToolRegistry(unittest.TestCase):

    def setUp(self):
        # Use the actual project dir so builtin tools resolve
        self.base = Path(__file__).resolve().parent.parent
        self.registry = ToolRegistry(self.base)

    def test_builtins_registered(self):
        self.assertIn("read_file", self.registry.tools)
        self.assertIn("write_file", self.registry.tools)
        self.assertIn("list_dir", self.registry.tools)
        self.assertIn("system_snapshot", self.registry.tools)

    def test_script_tools_discovered(self):
        # Should find tools/run/*.py scripts
        script_tools = [k for k in self.registry.tools if k.startswith("run_")]
        self.assertGreater(len(script_tools), 0)
        self.assertIn("run_read", self.registry.tools)

    def test_execute_unknown(self):
        result = self.registry.execute("nonexistent_tool", [])
        self.assertIn("[TOOL ERROR]", result)
        self.assertIn("Unknown tool", result)

    def test_describe(self):
        desc = self.registry.describe()
        self.assertIn("read_file", desc)
        self.assertIn("run_read", desc)

    def test_get_side_effect(self):
        self.assertEqual(self.registry.get_side_effect("read_file"), "read")
        # Unknown tools default to "exec"
        self.assertEqual(self.registry.get_side_effect("fake_tool"), "exec")

    def test_execute_read_file(self):
        # Test actual execution of read_file builtin
        result = self.registry.execute("read_file", [str(self.base / "run.py")])
        self.assertNotIn("[TOOL ERROR]", result)

    def test_execute_list_dir(self):
        result = self.registry.execute("list_dir", [str(self.base)])
        self.assertNotIn("[TOOL ERROR]", result)


class TestScriptTool(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.script = os.path.join(self.tmp, "echo.py")
        with open(self.script, "w") as f:
            f.write('import sys\nprint("ECHO:", *sys.argv[1:])\n')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run(self):
        spec = ToolSpec("run_echo", "Echo args", ["text"], "read")
        tool = ScriptTool("echo", Path(self.script), spec)
        result = tool.run("hello", "world")
        self.assertIn("ECHO:", result)
        self.assertIn("hello", result)

    def test_timeout(self):
        # Script that hangs
        hang = os.path.join(self.tmp, "hang.py")
        with open(hang, "w") as f:
            f.write("import time; time.sleep(60)\n")
        spec = ToolSpec("run_hang", "Hangs", timeout_seconds=1)
        tool = ScriptTool("hang", Path(hang), spec)
        result = tool.run()
        self.assertIn("[TOOL ERROR]", result)
        self.assertIn("timed out", result)


if __name__ == "__main__":
    unittest.main()

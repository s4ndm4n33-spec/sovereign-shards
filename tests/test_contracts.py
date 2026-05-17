# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for core contracts (app.agent.contracts)."""

import unittest

from app.agent.contracts import AgentStep, AgentTask, ToolCall, ToolResult


class TestAgentStep(unittest.TestCase):

    def test_frozen(self):
        s = AgentStep("id1", "goal", "criteria")
        with self.assertRaises(AttributeError):
            s.id = "new"

    def test_default_depends_on(self):
        s = AgentStep("id1", "goal", "criteria")
        self.assertEqual(s.depends_on, ())


class TestToolCall(unittest.TestCase):

    def test_default_args(self):
        tc = ToolCall("run_read")
        self.assertEqual(tc.args, {})


class TestToolResult(unittest.TestCase):

    def test_ok(self):
        tr = ToolResult("run_read", True, "file content")
        self.assertTrue(tr.ok)
        self.assertEqual(tr.error, "")

    def test_error(self):
        tr = ToolResult("run_read", False, "", error="not found")
        self.assertFalse(tr.ok)


class TestAgentTask(unittest.TestCase):

    def test_defaults(self):
        t = AgentTask("build app")
        self.assertEqual(t.mode, "manual")
        self.assertEqual(t.steps, [])
        self.assertEqual(t.completed_step_ids, [])


if __name__ == "__main__":
    unittest.main()

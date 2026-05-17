# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for executor (app.agent.executor)."""

import unittest
from unittest import mock

from app.agent.contracts import AgentStep, ToolCall, ToolResult
from app.agent.executor import (
    build_step_prompt,
    needs_confirmation,
    execute_tool_call,
    format_tool_result,
)


class TestBuildStepPrompt(unittest.TestCase):

    def test_contains_step_info(self):
        step = AgentStep("s1", "Read the config", "Config loaded")
        prompt = build_step_prompt(step, "- run_read(path) [read]")
        self.assertIn("Read the config", prompt)
        self.assertIn("Config loaded", prompt)
        self.assertIn("run_read", prompt)


class TestNeedsConfirmation(unittest.TestCase):

    def _mock_registry(self, side_effect="read"):
        reg = mock.MagicMock()
        reg.get_side_effect.return_value = side_effect
        return reg

    def test_manual_always(self):
        self.assertTrue(needs_confirmation("run_read", self._mock_registry(), "manual"))

    def test_auto_full_never(self):
        self.assertFalse(needs_confirmation("run_bash", self._mock_registry("exec"), "auto-full"))

    def test_auto_safe_blocks_exec(self):
        self.assertTrue(needs_confirmation("run_bash", self._mock_registry("exec"), "auto-safe"))

    def test_auto_safe_allows_read(self):
        self.assertFalse(needs_confirmation("run_read", self._mock_registry("read"), "auto-safe"))

    def test_semi_blocks_write(self):
        self.assertTrue(needs_confirmation("run_write", self._mock_registry("write"), "semi"))

    def test_semi_allows_read(self):
        self.assertFalse(needs_confirmation("run_read", self._mock_registry("read"), "semi"))


class TestExecuteToolCall(unittest.TestCase):

    @mock.patch("app.agent.executor.PROCESS_PAUSE_SECONDS", 0)
    def test_success(self):
        reg = mock.MagicMock()
        reg.execute.return_value = "file content here"
        call = ToolCall("run_read", {"path": "test.py"})
        result = execute_tool_call(call, reg)
        self.assertTrue(result.ok)
        self.assertIn("file content", result.output)

    @mock.patch("app.agent.executor.PROCESS_PAUSE_SECONDS", 0)
    def test_error(self):
        reg = mock.MagicMock()
        reg.execute.return_value = "[TOOL ERROR] file not found"
        call = ToolCall("run_read", {"path": "missing.py"})
        result = execute_tool_call(call, reg)
        self.assertFalse(result.ok)
        self.assertIn("TOOL ERROR", result.error)


class TestFormatToolResult(unittest.TestCase):

    def test_ok_format(self):
        tr = ToolResult("run_read", True, "hello world")
        text = format_tool_result(tr)
        self.assertIn("[TOOL OK]", text)
        self.assertIn("hello world", text)

    def test_error_format(self):
        tr = ToolResult("run_bash", False, "", error="segfault")
        text = format_tool_result(tr)
        self.assertIn("[TOOL ERROR]", text)
        self.assertIn("segfault", text)


if __name__ == "__main__":
    unittest.main()

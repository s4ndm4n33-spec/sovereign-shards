# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for planner (app.agent.planner)."""

import json
import unittest

from app.agent.planner import parse_plan, build_plan_prompt


class TestBuildPrompt(unittest.TestCase):

    def test_contains_objective(self):
        prompt = build_plan_prompt("Fix the login page")
        self.assertIn("Fix the login page", prompt)

    def test_contains_json_instruction(self):
        prompt = build_plan_prompt("anything")
        self.assertIn("JSON array", prompt)


class TestParsePlan(unittest.TestCase):

    def test_valid_json(self):
        raw = json.dumps([
            {"id": "s1", "goal": "Read file", "success_criteria": "loaded", "depends_on": []},
            {"id": "s2", "goal": "Edit file", "success_criteria": "saved", "depends_on": ["s1"]},
        ])
        task = parse_plan(raw, "fix bug")
        self.assertEqual(len(task.steps), 2)
        self.assertEqual(task.steps[0].id, "s1")
        self.assertEqual(task.steps[1].depends_on, ("s1",))

    def test_json_in_markdown_fences(self):
        raw = '```json\n[{"id": "a", "goal": "Do thing", "success_criteria": "done", "depends_on": []}]\n```'
        task = parse_plan(raw, "test")
        self.assertEqual(len(task.steps), 1)

    def test_fallback_on_garbage(self):
        task = parse_plan("This is not JSON at all", "my objective")
        self.assertEqual(len(task.steps), 1)
        self.assertIn("my objective", task.steps[0].goal)

    def test_empty_json_array(self):
        task = parse_plan("[]", "obj")
        # Falls back to single step
        self.assertEqual(len(task.steps), 1)

    def test_mode_preserved(self):
        raw = '[{"id": "x", "goal": "g", "success_criteria": "c", "depends_on": []}]'
        task = parse_plan(raw, "obj", mode="auto-full")
        self.assertEqual(task.mode, "auto-full")


if __name__ == "__main__":
    unittest.main()

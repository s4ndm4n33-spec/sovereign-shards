"""Tests for reflection (app.agent.reflection)."""

import json
import unittest

from app.agent.reflection import build_reflect_prompt, parse_reflected


class TestBuildReflectPrompt(unittest.TestCase):

    def test_contains_entry_count(self):
        entries = [{"step": f"s{i}", "result": "ok"} for i in range(10)]
        prompt = build_reflect_prompt(entries, target=3)
        self.assertIn("10", prompt)
        self.assertIn("3", prompt)

    def test_contains_entries(self):
        entries = [{"step": "read config", "result": "loaded db settings"}]
        prompt = build_reflect_prompt(entries)
        self.assertIn("read config", prompt)


class TestParseReflected(unittest.TestCase):

    def test_valid_json(self):
        raw = json.dumps([
            {"step": "summarised step", "result": "key outcome", "decision": "chose X"},
        ])
        result = parse_reflected(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["step"], "summarised step")
        self.assertEqual(result[0]["decision"], "chose X")

    def test_strips_fences(self):
        raw = '```json\n[{"step": "a", "result": "b"}]\n```'
        result = parse_reflected(raw)
        self.assertEqual(len(result), 1)

    def test_garbage(self):
        result = parse_reflected("this is not json")
        self.assertEqual(result, [])

    def test_missing_required_fields(self):
        raw = json.dumps([{"step": "ok"}])  # missing "result"
        result = parse_reflected(raw)
        self.assertEqual(len(result), 0)

    def test_optional_fields(self):
        raw = json.dumps([{"step": "s", "result": "r", "issue": "i"}])
        result = parse_reflected(raw)
        self.assertEqual(result[0]["issue"], "i")
        self.assertNotIn("decision", result[0])


if __name__ == "__main__":
    unittest.main()

# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for context management (app.agent.context)."""

import unittest

from app.agent.context import estimate_tokens, trim_context


class TestEstimateTokens(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(estimate_tokens("abcd"), 1)

    def test_longer(self):
        self.assertEqual(estimate_tokens("a" * 400), 100)

    def test_empty(self):
        self.assertEqual(estimate_tokens(""), 1)  # min 1


class TestTrimContext(unittest.TestCase):

    def _msgs(self, n, role="user", length=100):
        return [{"role": role, "content": "x" * length} for _ in range(n)]

    def test_under_budget(self):
        msgs = self._msgs(3, length=10)
        result = trim_context(msgs, max_tokens=1000)
        self.assertEqual(len(result), 3)

    def test_trims_middle(self):
        msgs = [{"role": "system", "content": "sys"}]
        msgs += self._msgs(20, length=200)
        result = trim_context(msgs, max_tokens=300, keep_last_n=2)
        # Should have system + summary + last 2
        self.assertLessEqual(len(result), 5)

    def test_keeps_system(self):
        msgs = [{"role": "system", "content": "I am J"}] + self._msgs(10, length=200)
        result = trim_context(msgs, max_tokens=200, keep_last_n=2)
        self.assertEqual(result[0]["role"], "system")
        self.assertIn("I am J", result[0]["content"])

    def test_empty_messages(self):
        self.assertEqual(trim_context([]), [])

    def test_summary_contains_compressed_marker(self):
        # Many long messages with a generous budget that can hold the summary
        msgs = [{"role": "system", "content": "s"}] + self._msgs(20, length=400)
        result = trim_context(msgs, max_tokens=1500, keep_last_n=2)
        texts = " ".join(m["content"] for m in result)
        self.assertIn("CONTEXT SUMMARY", texts)


if __name__ == "__main__":
    unittest.main()

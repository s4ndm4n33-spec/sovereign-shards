# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for BM25 retriever (app.agent.retriever)."""

import unittest

from app.agent.retriever import tokenize, bm25_score, retrieve


class TestTokenize(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(tokenize("Hello World"), ["hello", "world"])

    def test_underscores(self):
        self.assertEqual(tokenize("my_var"), ["my_var"])

    def test_mixed(self):
        tokens = tokenize("Fix bug #42 in parser.py!")
        self.assertIn("fix", tokens)
        self.assertIn("42", tokens)
        self.assertIn("parser", tokens)

    def test_empty(self):
        self.assertEqual(tokenize(""), [])


class TestBM25Score(unittest.TestCase):

    def test_nonzero_match(self):
        query = ["python", "bug"]
        doc = ["python", "has", "a", "bug", "in", "parser"]
        score = bm25_score(query, doc, {"python": 1, "bug": 1}, 3, 6.0)
        self.assertGreater(score, 0)

    def test_zero_no_match(self):
        query = ["java"]
        doc = ["python", "parser"]
        score = bm25_score(query, doc, {"python": 1, "parser": 1}, 2, 3.0)
        self.assertEqual(score, 0.0)


class TestRetrieve(unittest.TestCase):

    def setUp(self):
        self.chunks = [
            {"step": "read config file", "result": "loaded database settings"},
            {"step": "fix parser bug", "result": "resolved index error in AST"},
            {"step": "deploy server", "result": "nginx started on port 8080"},
            {"step": "write unit tests", "result": "added tests for parser module"},
            {"step": "update readme", "result": "documented new API endpoints"},
        ]

    def test_relevance_ranking(self):
        results = retrieve("parser bug fix", self.chunks, top_k=2)
        self.assertEqual(len(results), 2)
        # Parser-related entries should rank highest
        top_steps = [r["step"] for r in results]
        self.assertIn("fix parser bug", top_steps)

    def test_top_k(self):
        results = retrieve("test", self.chunks, top_k=1)
        self.assertEqual(len(results), 1)

    def test_empty_query(self):
        results = retrieve("", self.chunks)
        self.assertEqual(results, [])

    def test_empty_chunks(self):
        results = retrieve("hello", [])
        self.assertEqual(results, [])

    def test_scores_present(self):
        results = retrieve("parser", self.chunks, top_k=3)
        for r in results:
            self.assertIn("_score", r)
            self.assertIsInstance(r["_score"], float)

    def test_scores_descending(self):
        results = retrieve("parser AST error", self.chunks, top_k=5)
        scores = [r["_score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()

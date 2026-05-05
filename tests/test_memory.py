"""Tests for Tier 3: Long-term memory (app.agent.memory)."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestMemory(unittest.TestCase):
    """Test remember / recall / forget with a temp file."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mem_path = Path(self.tmp) / "memory.json"
        self._patches = [
            mock.patch("app.agent.memory.MEMORY_PATH", self.mem_path),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        if self.mem_path.exists():
            os.unlink(self.mem_path)
        os.rmdir(self.tmp)

    def test_remember_and_recall(self):
        from app.agent.memory import remember, recall
        remember("lang", "python")
        self.assertEqual(recall("lang"), "python")

    def test_recall_missing(self):
        from app.agent.memory import recall
        self.assertIsNone(recall("nonexistent"))

    def test_forget(self):
        from app.agent.memory import remember, recall, forget
        remember("key", "val")
        self.assertTrue(forget("key"))
        self.assertIsNone(recall("key"))

    def test_forget_nonexistent(self):
        from app.agent.memory import forget
        self.assertFalse(forget("nope"))

    def test_recall_all(self):
        from app.agent.memory import remember, recall_all
        remember("a", "1")
        remember("b", "2")
        data = recall_all()
        self.assertEqual(data, {"a": "1", "b": "2"})

    def test_overwrite(self):
        from app.agent.memory import remember, recall
        remember("key", "old")
        remember("key", "new")
        self.assertEqual(recall("key"), "new")

    def test_size_cap_prunes(self):
        from app.agent.memory import remember, recall_all
        # Patch cap to something tiny
        with mock.patch("app.agent.memory.MAX_MEMORY_BYTES", 100):
            for i in range(50):
                remember(f"k{i}", "x" * 20)
            data = recall_all()
            raw = json.dumps(data, indent=2).encode("utf-8")
            self.assertLessEqual(len(raw), 200)  # generous margin

    def test_atomic_write(self):
        from app.agent.memory import remember
        remember("test", "atomic")
        # .tmp should not linger
        tmps = list(Path(self.tmp).glob("*.tmp"))
        self.assertEqual(tmps, [])


class TestWorkingMemory(unittest.TestCase):
    """Test Tier 2: Working memory (app.agent.working_memory)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.wm_path = Path(self.tmp) / "working_memory.jsonl"
        self._patches = [
            mock.patch("app.agent.working_memory.WM_PATH", self.wm_path),
            mock.patch("app.agent.working_memory.MEMORY_DIR", Path(self.tmp)),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        if self.wm_path.exists():
            os.unlink(self.wm_path)
        os.rmdir(self.tmp)

    def test_append_and_read(self):
        from app.agent.working_memory import append, read_all
        append("step1", "ok")
        append("step2", "fail", issue="crash")
        entries = read_all()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["step"], "step1")
        self.assertEqual(entries[1]["issue"], "crash")

    def test_read_recent(self):
        from app.agent.working_memory import append, read_recent
        for i in range(10):
            append(f"s{i}", "ok")
        recent = read_recent(3)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0]["step"], "s7")

    def test_empty_read(self):
        from app.agent.working_memory import read_all
        self.assertEqual(read_all(), [])

    def test_needs_reflection(self):
        from app.agent.working_memory import append, needs_reflection
        with mock.patch("app.agent.working_memory.MAX_WM_BYTES", 50):
            for i in range(20):
                append(f"step{i}", "result" * 10)
            self.assertTrue(needs_reflection())

    def test_replace_entries(self):
        from app.agent.working_memory import append, replace_entries, read_all
        append("old", "data")
        replace_entries([{"step": "new", "result": "compressed"}])
        entries = read_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["step"], "new")

    def test_compress_turn(self):
        from app.agent.working_memory import compress_turn
        entry = compress_turn(
            "fix the bug in parser.py",
            "Fixed: was using wrong index. Decided to use enumerate instead."
        )
        self.assertIn("fix the bug", entry["step"])
        self.assertIsNotNone(entry["decision"])

    def test_compress_turn_with_error(self):
        from app.agent.working_memory import compress_turn
        entry = compress_turn("deploy", "ERROR: connection refused on port 8080")
        self.assertIsNotNone(entry["issue"])

    def test_format_for_context(self):
        from app.agent.working_memory import format_for_context
        entries = [{"step": "read file", "result": "ok", "issue": "slow"}]
        text = format_for_context(entries)
        self.assertIn("[WORKING MEMORY", text)
        self.assertIn("read file", text)
        self.assertIn("⚠", text)

    def test_format_empty(self):
        from app.agent.working_memory import format_for_context
        self.assertEqual(format_for_context([]), "")


if __name__ == "__main__":
    unittest.main()

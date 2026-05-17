# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for the file-based task buffer."""

import json
import os
import sys
from pathlib import Path

# Make sure app/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.agent import task_buffer


@pytest.fixture(autouse=True)
def clean_buffer(tmp_path):
    """Redirect the buffer to a temp directory and clean up after."""
    original = task_buffer.BUFFER_PATH
    task_buffer.BUFFER_PATH = tmp_path / "task_buffer.jsonl"
    task_buffer.MEMORY_DIR = tmp_path
    yield
    task_buffer.BUFFER_PATH = original
    task_buffer.MEMORY_DIR = task_buffer.BASE_DIR / "memory"


class TestWriteAndRead:
    def test_write_and_read_plan(self):
        steps = [
            {"id": "s1", "goal": "Read the file"},
            {"id": "s2", "goal": "Fix the bug", "depends": ["s1"]},
        ]
        n = task_buffer.write_plan(steps)
        assert n == 2

        all_steps = task_buffer.read_all()
        assert len(all_steps) == 2
        assert all_steps[0]["id"] == "s1"
        assert all_steps[0]["status"] == "pending"
        assert all_steps[1]["depends"] == ["s1"]

    def test_write_caps_at_max_steps(self):
        steps = [{"id": f"s{i}", "goal": f"Step {i}"} for i in range(20)]
        n = task_buffer.write_plan(steps)
        assert n == task_buffer.MAX_STEPS
        assert len(task_buffer.read_all()) == task_buffer.MAX_STEPS

    def test_empty_buffer_returns_empty(self):
        assert task_buffer.read_all() == []

    def test_overwrite_replaces(self):
        task_buffer.write_plan([{"id": "s1", "goal": "First"}])
        task_buffer.write_plan([{"id": "s1", "goal": "Second"}])
        all_steps = task_buffer.read_all()
        assert len(all_steps) == 1
        assert all_steps[0]["goal"] == "Second"


class TestNextStep:
    def test_next_returns_first_pending(self):
        task_buffer.write_plan([
            {"id": "s1", "goal": "First"},
            {"id": "s2", "goal": "Second", "depends": ["s1"]},
        ])
        step = task_buffer.next_step()
        assert step["id"] == "s1"

    def test_next_respects_dependencies(self):
        task_buffer.write_plan([
            {"id": "s1", "goal": "First"},
            {"id": "s2", "goal": "Second", "depends": ["s1"]},
        ])
        task_buffer.mark_done("s1", "done")
        step = task_buffer.next_step()
        assert step["id"] == "s2"

    def test_next_returns_none_when_blocked(self):
        task_buffer.write_plan([
            {"id": "s1", "goal": "First"},
            {"id": "s2", "goal": "Second", "depends": ["s1"]},
        ])
        # s1 still pending, s2 blocked → next returns s1
        step = task_buffer.next_step()
        assert step["id"] == "s1"

    def test_next_returns_none_when_all_done(self):
        task_buffer.write_plan([{"id": "s1", "goal": "Only"}])
        task_buffer.mark_done("s1", "complete")
        assert task_buffer.next_step() is None


class TestMarkDoneAndFailed:
    def test_mark_done(self):
        task_buffer.write_plan([{"id": "s1", "goal": "Do thing"}])
        task_buffer.mark_done("s1", "It worked")
        step = task_buffer.read_all()[0]
        assert step["status"] == "done"
        assert step["result"] == "It worked"
        assert step["ts"] is not None

    def test_mark_failed(self):
        task_buffer.write_plan([{"id": "s1", "goal": "Do thing"}])
        task_buffer.mark_failed("s1", "Broke")
        step = task_buffer.read_all()[0]
        assert step["status"] == "failed"
        assert step["result"] == "Broke"


class TestCounts:
    def test_is_complete(self):
        task_buffer.write_plan([
            {"id": "s1", "goal": "A"},
            {"id": "s2", "goal": "B"},
        ])
        assert not task_buffer.is_complete()
        task_buffer.mark_done("s1", "ok")
        assert not task_buffer.is_complete()
        task_buffer.mark_done("s2", "ok")
        assert task_buffer.is_complete()

    def test_counts(self):
        task_buffer.write_plan([
            {"id": "s1", "goal": "A"},
            {"id": "s2", "goal": "B"},
            {"id": "s3", "goal": "C"},
        ])
        assert task_buffer.pending_count() == 3
        assert task_buffer.done_count() == 0
        assert task_buffer.failed_count() == 0

        task_buffer.mark_done("s1", "ok")
        task_buffer.mark_failed("s2", "nope")
        assert task_buffer.pending_count() == 1
        assert task_buffer.done_count() == 1
        assert task_buffer.failed_count() == 1

    def test_empty_is_complete(self):
        assert task_buffer.is_complete()


class TestSummary:
    def test_summary_format(self):
        task_buffer.write_plan([
            {"id": "s1", "goal": "Read file"},
            {"id": "s2", "goal": "Fix bug"},
        ])
        task_buffer.mark_done("s1", "Content loaded")
        s = task_buffer.summary()
        assert "✓ s1" in s
        assert "… s2" in s
        assert "Content loaded" in s

    def test_empty_summary(self):
        s = task_buffer.summary()
        assert "Empty" in s


class TestStepPrompt:
    def test_basic_prompt(self):
        task_buffer.write_plan([{"id": "s1", "goal": "Read app/chat.py"}])
        step = task_buffer.next_step()
        prompt = task_buffer.step_prompt(step)
        assert "s1" in prompt
        assert "Read app/chat.py" in prompt
        assert "ONE tool" in prompt

    def test_prompt_includes_dependency_results(self):
        task_buffer.write_plan([
            {"id": "s1", "goal": "Search"},
            {"id": "s2", "goal": "Read", "depends": ["s1"]},
        ])
        task_buffer.mark_done("s1", "Found 3 matches in chat.py")
        step = task_buffer.next_step()
        prompt = task_buffer.step_prompt(step)
        assert "Found 3 matches" in prompt


class TestParsing:
    def test_parse_numbered_plan(self):
        text = """Here's my plan:
1. Read the router code
2. Add the new route
3. Test it works
"""
        steps = task_buffer.parse_numbered_plan(text)
        assert len(steps) == 3
        assert steps[0]["goal"] == "Read the router code"
        assert steps[0]["depends"] == []
        assert steps[1]["depends"] == ["s1"]
        assert steps[2]["depends"] == ["s2"]

    def test_parse_parentheses_format(self):
        text = "1) Search for the bug\n2) Read the file\n3) Fix it"
        steps = task_buffer.parse_numbered_plan(text)
        assert len(steps) == 3

    def test_parse_step_prefix_format(self):
        text = "Step 1: Search\nStep 2: Read\nStep 3: Fix"
        steps = task_buffer.parse_numbered_plan(text)
        assert len(steps) == 3

    def test_parse_empty_text(self):
        assert task_buffer.parse_numbered_plan("no steps here") == []

    def test_parse_tool_commands(self):
        text = """run_search should_reflect app/chat.py
run_read app/chat.py
# this is a comment
write_file app/chat.py content here
"""
        steps = task_buffer.parse_tool_commands(text)
        assert len(steps) == 3
        assert steps[0]["goal"] == "run_search should_reflect app/chat.py"
        assert steps[2]["goal"] == "write_file app/chat.py content here"

    def test_parse_tool_commands_skips_empty(self):
        assert task_buffer.parse_tool_commands("") == []
        assert task_buffer.parse_tool_commands("\n\n") == []


class TestClear:
    def test_clear(self):
        task_buffer.write_plan([{"id": "s1", "goal": "A"}])
        assert len(task_buffer.read_all()) == 1
        task_buffer.clear()
        assert len(task_buffer.read_all()) == 0

    def test_clear_nonexistent(self):
        task_buffer.clear()  # should not raise

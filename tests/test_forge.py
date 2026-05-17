# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for tool forge (app.agent.tool_forge + tool_researcher)."""

import json
import os
import tempfile
import unittest

from app.agent.tool_researcher import (
    ToolSpec,
    needs_new_tool,
    build_research_prompt,
    parse_research,
    _slugify,
)
from app.agent.tool_forge import (
    build_forge_prompt,
    assemble_tool_code,
    validate_tool,
    ForgeResult,
    log_forge_event,
    _make_test_args,
)


# ── Researcher tests ─────────────────────────────────────

class TestNeedsNewTool(unittest.TestCase):

    def _mock_registry(self, names=None):
        from unittest import mock
        reg = mock.MagicMock()
        reg.specs = {n: None for n in (names or ["run_read", "run_write", "run_bash"])}
        return reg

    def test_explicit_trigger(self):
        reg = self._mock_registry()
        self.assertTrue(needs_new_tool("build a tool for making STL files", reg))

    def test_create_trigger(self):
        reg = self._mock_registry()
        self.assertTrue(needs_new_tool("create a script for PDF merging", reg))

    def test_existing_tool_mentioned(self):
        reg = self._mock_registry()
        # "read" matches run_read
        self.assertFalse(needs_new_tool("read the config file", reg))

    def test_no_match_heuristic(self):
        reg = self._mock_registry()
        self.assertTrue(needs_new_tool("generate a fractal image", reg))


class TestBuildResearchPrompt(unittest.TestCase):

    def test_contains_request(self):
        prompt = build_research_prompt("make STL files", "- run_read [read]", [])
        self.assertIn("make STL files", prompt)
        self.assertIn("run_read", prompt)

    def test_with_local_hits(self):
        hits = [{"text": "stl related code", "_score": 2.5}]
        prompt = build_research_prompt("stl", "- tools", hits)
        self.assertIn("stl related code", prompt)


class TestParseResearch(unittest.TestCase):

    def test_valid_json(self):
        raw = json.dumps([{
            "tool_name": "stl_planner",
            "purpose": "Plan STL geometry",
            "inputs": ["shape: str"],
            "outputs": ["stl path"],
            "dependencies": [],
            "companion_tools": ["stl_forge"],
            "example_call": "run_stl_planner('cube')",
        }])
        result = parse_research(raw, "make STL files")
        self.assertEqual(len(result.specs), 1)
        self.assertEqual(result.specs[0].tool_name, "stl_planner")

    def test_fallback_on_garbage(self):
        result = parse_research("not json at all", "my request")
        self.assertEqual(len(result.specs), 1)  # fallback
        self.assertIn("my_request", result.specs[0].tool_name)

    def test_json_in_fences(self):
        raw = '```json\n[{"tool_name": "csv_parser", "purpose": "Parse CSV", "inputs": ["path: str"], "outputs": ["data"], "dependencies": [], "companion_tools": [], "example_call": ""}]\n```'
        result = parse_research(raw, "parse csv")
        self.assertEqual(result.specs[0].tool_name, "csv_parser")


class TestSlugify(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(_slugify("Make STL Files"), "make_stl_files")

    def test_special_chars(self):
        slug = _slugify("what's up?!")
        self.assertTrue(slug.replace("_", "").isalnum())

    def test_empty(self):
        self.assertEqual(_slugify(""), "custom_tool")


# ── Forge tests ──────────────────────────────────────────

class TestBuildForgePrompt(unittest.TestCase):

    def test_contains_spec_details(self):
        spec = ToolSpec("csv_parser", "Parse CSV files", ["path: str"], ["rows"])
        prompt = build_forge_prompt(spec)
        self.assertIn("csv_parser", prompt)
        self.assertIn("Parse CSV", prompt)
        self.assertIn("path", prompt)


class TestAssembleToolCode(unittest.TestCase):

    def test_wraps_implementation(self):
        spec = ToolSpec("hello", "Say hello")
        impl = 'def run() -> str:\n    return "Hello!"'
        code = assemble_tool_code(spec, impl)
        self.assertIn("TOOL_NAME", code)
        self.assertIn("run_hello", code)
        self.assertIn('return "Hello!"', code)
        self.assertIn("__main__", code)

    def test_strips_markdown_fences(self):
        spec = ToolSpec("test", "Test tool")
        impl = '```python\ndef run() -> str:\n    return "ok"\n```'
        code = assemble_tool_code(spec, impl)
        self.assertNotIn("```", code)


class TestValidateTool(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_valid_tool(self):
        spec = ToolSpec("greeter", "Greet", ["name: str"], ["greeting"])
        code = (
            'import os\nimport sys\n\n'
            'TOOL_NAME = "run_greeter"\n'
            'TOOL_DESC = "Greet"\n\n'
            'def run(name="world") -> str:\n'
            '    return f"Hello {name}!"\n\n'
            'if __name__ == "__main__":\n'
            '    args = sys.argv[1:]\n'
            '    try:\n'
            '        print(run(*args))\n'
            '    except Exception as exc:\n'
            '        print(f"[TOOL ERROR] {exc}")\n'
            '        sys.exit(1)\n'
        )
        passed, error = validate_tool(code, spec, self.tmp)
        self.assertTrue(passed, f"Validation failed: {error}")

    def test_syntax_error_fails(self):
        spec = ToolSpec("bad", "Bad tool")
        code = 'TOOL_NAME = "run_bad"\ndef run( -> str:\n'
        passed, error = validate_tool(code, spec, self.tmp)
        self.assertFalse(passed)
        self.assertIn("yntax", error)  # "Syntax" or "syntax"

    def test_missing_run_fails(self):
        spec = ToolSpec("nofunc", "No func")
        code = 'TOOL_NAME = "run_nofunc"\nx = 1\n'
        passed, error = validate_tool(code, spec, self.tmp)
        self.assertFalse(passed)
        self.assertIn("run()", error)

    def test_missing_tool_name_fails(self):
        spec = ToolSpec("noname", "No name")
        code = 'def run() -> str:\n    return "ok"\n'
        passed, error = validate_tool(code, spec, self.tmp)
        self.assertFalse(passed)
        self.assertIn("TOOL_NAME", error)


class TestMakeTestArgs(unittest.TestCase):

    def test_int_arg(self):
        spec = ToolSpec("t", "t", ["count: int"])
        args = _make_test_args(spec)
        self.assertEqual(args, ["1"])

    def test_path_arg(self):
        spec = ToolSpec("t", "t", ["file_path: str"])
        args = _make_test_args(spec)
        self.assertEqual(args, ["__test_nonexistent__"])

    def test_string_arg(self):
        spec = ToolSpec("t", "t", ["name: str"])
        args = _make_test_args(spec)
        self.assertEqual(args, ["test_input"])


class TestLogForgeEvent(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_log(self):
        spec = ToolSpec("logger_test", "Test logging")
        result = ForgeResult("run_logger_test", True, "tools/run/logger_test.py", attempts=1)
        log_forge_event(result, spec, self.tmp)

        log_path = os.path.join(self.tmp, "logs", "tool_forge.jsonl")
        self.assertTrue(os.path.exists(log_path))

        with open(log_path) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["tool_name"], "run_logger_test")
        self.assertTrue(entry["success"])


if __name__ == "__main__":
    unittest.main()

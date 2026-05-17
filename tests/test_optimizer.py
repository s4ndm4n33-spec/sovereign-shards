# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for the Five Masters Code Optimizer.

Coverage: transforms (each deterministic fix), pipeline stages,
revert logic, dry-run mode, batch processing.
"""

import ast
import os
import tempfile
import textwrap

import pytest

# ── Transform unit tests ─────────────────────────────────────────────

from app.agent.transforms import (
    fix_range_len,
    fix_bare_except,
    fix_silent_except,
    fix_mutable_default,
    fix_unguarded_io,
    apply_all_deterministic,
    TransformResult,
)


class TestKorotkevichTransform:
    """Korotkevich: range(len()) → enumerate()."""

    def test_basic_range_len(self):
        code = textwrap.dedent("""\
            items = [1, 2, 3]
            for i in range(len(items)):
                print(items[i])
        """)
        tree = ast.parse(code)
        new_tree, results = fix_range_len(tree)
        output = ast.unparse(new_tree)
        assert "enumerate" in output
        assert "range(len" not in output
        assert len(results) == 1
        assert results[0].applied

    def test_no_range_len(self):
        code = "for x in [1, 2, 3]:\n    print(x)\n"
        tree = ast.parse(code)
        _, results = fix_range_len(tree)
        assert len(results) == 0

    def test_range_without_len(self):
        code = "for i in range(10):\n    print(i)\n"
        tree = ast.parse(code)
        _, results = fix_range_len(tree)
        assert len(results) == 0


class TestTorvaldsTransform:
    """Torvalds: bare except and silent except fixes."""

    def test_bare_except_pass(self):
        code = textwrap.dedent("""\
            try:
                x = 1
            except:
                pass
        """)
        tree = ast.parse(code)
        new_tree, results = fix_bare_except(tree)
        output = ast.unparse(new_tree)
        assert "except Exception" in output
        assert "raise" in output
        assert len(results) == 1

    def test_bare_except_with_code(self):
        code = textwrap.dedent("""\
            try:
                x = 1
            except:
                x = 0
        """)
        tree = ast.parse(code)
        new_tree, results = fix_bare_except(tree)
        output = ast.unparse(new_tree)
        assert "except Exception" in output
        assert len(results) == 1

    def test_silent_except_exception(self):
        code = textwrap.dedent("""\
            try:
                x = 1
            except Exception:
                x = 0
        """)
        tree = ast.parse(code)
        new_tree, results = fix_silent_except(tree)
        output = ast.unparse(new_tree)
        assert "print" in output or "error" in output
        assert len(results) == 1

    def test_except_with_logging_untouched(self):
        code = textwrap.dedent("""\
            try:
                x = 1
            except Exception as e:
                print(e)
        """)
        tree = ast.parse(code)
        _, results = fix_silent_except(tree)
        assert len(results) == 0

    def test_except_with_raise_untouched(self):
        code = textwrap.dedent("""\
            try:
                x = 1
            except Exception as e:
                raise
        """)
        tree = ast.parse(code)
        _, results = fix_silent_except(tree)
        assert len(results) == 0


class TestCarmackTransform:
    """Carmack: mutable default arguments."""

    def test_list_default(self):
        code = textwrap.dedent("""\
            def process(items=[]):
                items.append(1)
                return items
        """)
        tree = ast.parse(code)
        new_tree, results = fix_mutable_default(tree)
        output = ast.unparse(new_tree)
        assert "None" in output
        assert "is None" in output
        assert len(results) == 1

    def test_dict_default(self):
        code = textwrap.dedent("""\
            def config(opts={}):
                return opts
        """)
        tree = ast.parse(code)
        new_tree, results = fix_mutable_default(tree)
        output = ast.unparse(new_tree)
        assert "None" in output
        assert len(results) == 1

    def test_immutable_default_untouched(self):
        code = textwrap.dedent("""\
            def greet(name="world"):
                print(name)
        """)
        tree = ast.parse(code)
        _, results = fix_mutable_default(tree)
        assert len(results) == 0


class TestHamiltonTransform:
    """Hamilton: unguarded I/O operations."""

    def test_unguarded_open(self):
        code = textwrap.dedent("""\
            f = open("test.txt")
            data = f.read()
        """)
        tree = ast.parse(code)
        new_tree, results = fix_unguarded_io(tree)
        output = ast.unparse(new_tree)
        assert "try:" in output or "except" in output
        assert len(results) >= 1

    def test_guarded_open_untouched(self):
        code = textwrap.dedent("""\
            try:
                f = open("test.txt")
            except OSError:
                pass
        """)
        tree = ast.parse(code)
        _, results = fix_unguarded_io(tree)
        assert len(results) == 0


class TestApplyAllDeterministic:
    """Full deterministic pipeline."""

    def test_multiple_fixes(self):
        code = textwrap.dedent("""\
            def process(data=[]):
                for i in range(len(data)):
                    try:
                        print(data[i])
                    except:
                        pass
        """)
        tree = ast.parse(code)
        new_tree, results = apply_all_deterministic(tree)
        output = ast.unparse(new_tree)
        applied = [r for r in results if r.applied]
        assert len(applied) >= 2  # at least mutable + bare except

    def test_clean_code_no_changes(self):
        code = textwrap.dedent("""\
            def greet(name: str) -> str:
                return f"Hello, {name}"
        """)
        tree = ast.parse(code)
        _, results = apply_all_deterministic(tree)
        applied = [r for r in results if r.applied]
        assert len(applied) == 0

    def test_output_is_valid_python(self):
        code = textwrap.dedent("""\
            def bad(items=[], cache={}):
                for i in range(len(items)):
                    try:
                        cache[i] = items[i]
                    except:
                        pass
                f = open("out.txt")
                return cache
        """)
        tree = ast.parse(code)
        new_tree, _ = apply_all_deterministic(tree)
        output = ast.unparse(new_tree)
        # Must still be valid Python
        ast.parse(output)


# ── Optimizer pipeline tests ─────────────────────────────────────────

from app.agent.optimizer import (
    optimize_file,
    optimize_directory,
    batch_summary,
    OptimizeResult,
    _analyse,
    _build_plan,
    _verify,
)


class TestAnalyse:
    """Stage 2: Analysis."""

    def test_clean_code(self):
        code = "x = 1\n"
        tree, report = _analyse(code)
        assert report.score() >= 4

    def test_bad_code_has_issues(self):
        code = textwrap.dedent("""\
            def f(data=[]):
                for i in range(len(data)):
                    try:
                        print(data[i])
                    except:
                        pass
        """)
        _, report = _analyse(code)
        assert len(report.issues) > 0


class TestPlan:
    """Stage 3: Plan."""

    def test_classifies_deterministic(self):
        code = textwrap.dedent("""\
            def f(data=[]):
                for i in range(len(data)):
                    try:
                        print(data[i])
                    except:
                        pass
        """)
        _, report = _analyse(code)
        plan = _build_plan(report)
        strategies = {p.strategy for p in plan}
        assert "deterministic" in strategies


class TestVerify:
    """Stage 5: Verification."""

    def test_valid_improvement_passes(self):
        original = textwrap.dedent("""\
            def f():
                try:
                    x = 1
                except:
                    pass
        """)
        optimized = textwrap.dedent("""\
            def f():
                try:
                    x = 1
                except Exception as e:
                    print(f"Error: {e}")
                    raise
        """)
        from core.fivemasters import evaluate_code
        before = evaluate_code(original)
        passed, reason, after = _verify(original, optimized, before)
        assert passed or after.score() >= before.score()

    def test_syntax_error_fails(self):
        before = _analyse("x = 1\n")[1]
        passed, reason, _ = _verify("x = 1\n", "def broken(:\n", before)
        assert not passed
        assert "syntax" in reason.lower()


class TestOptimizeFile:
    """Full pipeline: file-based optimization."""

    def _write_temp(self, code: str) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8")
        f.write(code)
        f.close()
        return f.name

    def test_optimizes_bad_file(self):
        code = textwrap.dedent("""\
            def process(items=[]):
                for i in range(len(items)):
                    try:
                        print(items[i])
                    except:
                        pass
        """)
        path = self._write_temp(code)
        try:
            result = optimize_file(path)
            assert isinstance(result, OptimizeResult)
            assert result.before_report.score() <= result.after_report.score()
            applied = [t for t in result.transforms_applied if t.applied]
            assert len(applied) >= 1
        finally:
            os.unlink(path)

    def test_clean_file_unchanged(self):
        code = textwrap.dedent("""\
            def greet(name: str) -> str:
                return f"Hello, {name}"
        """)
        path = self._write_temp(code)
        try:
            result = optimize_file(path)
            assert result.optimized_source == result.original_source
        finally:
            os.unlink(path)

    def test_dry_run_no_changes(self):
        code = textwrap.dedent("""\
            def f(data=[]):
                pass
        """)
        path = self._write_temp(code)
        try:
            result = optimize_file(path, dry_run=True)
            assert result.optimized_source == result.original_source
        finally:
            os.unlink(path)

    def test_syntax_error_rejected(self):
        path = self._write_temp("def broken(\n")
        try:
            result = optimize_file(path)
            assert result.reverted
            assert "yntax" in result.revert_reason
        finally:
            os.unlink(path)

    def test_summary_output(self):
        code = textwrap.dedent("""\
            def f(data=[]):
                try:
                    x = 1
                except:
                    pass
        """)
        path = self._write_temp(code)
        try:
            result = optimize_file(path)
            summary = result.summary()
            assert "Five Masters" in summary
            assert "Before:" in summary
            assert "After:" in summary
        finally:
            os.unlink(path)

    def test_diff_output(self):
        code = textwrap.dedent("""\
            def f(data=[]):
                try:
                    x = 1
                except:
                    pass
        """)
        path = self._write_temp(code)
        try:
            result = optimize_file(path)
            if result.optimized_source != result.original_source:
                d = result.diff()
                assert "---" in d or "++" in d
        finally:
            os.unlink(path)


class TestOptimizeDirectory:
    """Batch directory optimization."""

    def test_batch_processes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Write a few test files
            Path = __import__("pathlib").Path
            (Path(tmp) / "good.py").write_text(
                "def greet(name: str) -> str:\n    return f'Hello, {name}'\n")
            (Path(tmp) / "bad.py").write_text(
                "def f(data=[]):\n    try:\n        x = 1\n    except:\n        pass\n")

            results = optimize_directory(tmp)
            assert len(results) == 2
            summary = batch_summary(results)
            assert "Files scanned:" in summary

    def test_skips_pycache(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path = __import__("pathlib").Path
            cache_dir = Path(tmp) / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "cached.py").write_text("x = 1\n")
            (Path(tmp) / "main.py").write_text("x = 1\n")

            results = optimize_directory(tmp)
            files = [r.file_path for r in results]
            assert len(results) == 1
            assert "cached" not in str(files)


# ── Ritchie transform tests ──────────────────────────────────────────

from app.agent.transforms import (
    fix_naming_funcs,
    fix_naming_classes,
)


class TestRitchieFuncNames:
    """Ritchie: camelCase functions → snake_case."""

    def test_camel_to_snake(self):
        code = textwrap.dedent("""\
            def processData(items):
                return items

            def getUserName():
                return "test"
        """)
        tree = ast.parse(code)
        new_tree, results = fix_naming_funcs(tree)
        output = ast.unparse(new_tree)
        assert "process_data" in output
        assert "get_user_name" in output
        assert "processData" not in output
        assert "getUserName" not in output
        assert len(results) == 2

    def test_already_snake_case(self):
        code = textwrap.dedent("""\
            def process_data(items):
                return items
        """)
        tree = ast.parse(code)
        _, results = fix_naming_funcs(tree)
        assert len(results) == 0

    def test_dunder_untouched(self):
        code = textwrap.dedent("""\
            def __init__(self):
                pass
        """)
        tree = ast.parse(code)
        _, results = fix_naming_funcs(tree)
        assert len(results) == 0

    def test_private_untouched(self):
        code = textwrap.dedent("""\
            def _helperMethod(self):
                pass
        """)
        tree = ast.parse(code)
        _, results = fix_naming_funcs(tree)
        assert len(results) == 0

    def test_call_sites_updated(self):
        code = textwrap.dedent("""\
            def processData(items):
                return items

            result = processData([1, 2, 3])
        """)
        tree = ast.parse(code)
        new_tree, results = fix_naming_funcs(tree)
        output = ast.unparse(new_tree)
        assert "process_data([1, 2, 3])" in output
        assert "processData" not in output

    def test_all_caps_untouched(self):
        code = textwrap.dedent("""\
            def CONSTANT():
                return 42
        """)
        tree = ast.parse(code)
        _, results = fix_naming_funcs(tree)
        assert len(results) == 0


class TestRitchieClassNames:
    """Ritchie: snake_case classes → PascalCase."""

    def test_snake_to_pascal(self):
        code = textwrap.dedent("""\
            class my_handler:
                pass
        """)
        tree = ast.parse(code)
        new_tree, results = fix_naming_classes(tree)
        output = ast.unparse(new_tree)
        assert "class MyHandler" in output
        assert "my_handler" not in output
        assert len(results) == 1

    def test_already_pascal(self):
        code = textwrap.dedent("""\
            class MyHandler:
                pass
        """)
        tree = ast.parse(code)
        _, results = fix_naming_classes(tree)
        assert len(results) == 0

    def test_references_updated(self):
        code = textwrap.dedent("""\
            class data_processor:
                def run(self):
                    pass

            obj = data_processor()
        """)
        tree = ast.parse(code)
        new_tree, results = fix_naming_classes(tree)
        output = ast.unparse(new_tree)
        assert "DataProcessor()" in output
        assert "data_processor" not in output

    def test_private_class_untouched(self):
        code = textwrap.dedent("""\
            class _internal_helper:
                pass
        """)
        tree = ast.parse(code)
        _, results = fix_naming_classes(tree)
        assert len(results) == 0

    def test_combined_output_valid(self):
        code = textwrap.dedent("""\
            class my_parser:
                def parseInput(self, raw):
                    return raw.strip()

            p = my_parser()
            result = p.parseInput("  hello  ")
        """)
        tree = ast.parse(code)
        new_tree, _ = apply_all_deterministic(tree)
        output = ast.unparse(new_tree)
        ast.parse(output)  # Must still be valid Python
        assert "MyParser" in output
        assert "parse_input" in output

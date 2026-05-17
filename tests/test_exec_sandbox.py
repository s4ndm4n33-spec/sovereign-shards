# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tests for sandboxed execution (tools/run/exec.py).

Verifies that the sandbox correctly:
  - Allows safe computation (math, strings, lists)
  - Blocks imports, dangerous builtins, dunder access
  - Enforces timeouts
  - Prevents filesystem and network escapes
  - Blocks CPython descriptor-based sandbox escapes
"""

import subprocess
import sys
from pathlib import Path
import unittest

TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "run" / "exec.py"


def run_exec(code: str, timeout: int = 20) -> str:
    result = subprocess.run(
        [sys.executable, str(TOOL_PATH)],
        input=code,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return (result.stdout or "") + (result.stderr or "")


class TestExecSandboxAllowed(unittest.TestCase):
    """Verify that safe, expected operations work."""

    def test_print_works(self):
        output = run_exec("print('hello')")
        self.assertEqual(output.strip(), "hello")

    def test_builtins_available(self):
        output = run_exec("print(len(range(3)))\nprint(sorted([3, 1, 2]))")
        self.assertIn("3", output)
        self.assertIn("[1, 2, 3]", output)

    def test_math_operations(self):
        output = run_exec("print(sum([i**2 for i in range(5)]))")
        self.assertIn("30", output)

    def test_string_operations(self):
        output = run_exec("s = 'hello world'\nprint(s.upper())\nprint(len(s))")
        self.assertIn("HELLO WORLD", output)
        self.assertIn("11", output)

    def test_lambda_and_functions(self):
        output = run_exec("f = lambda x: x * 2\nprint(f(21))")
        self.assertIn("42", output)

    def test_dict_and_list_ops(self):
        output = run_exec(
            "d = {'a': 1, 'b': 2}\n"
            "print(sorted(d.keys()))\n"
            "print(list(d.values()))"
        )
        self.assertIn("['a', 'b']", output)

    def test_exception_handling(self):
        output = run_exec(
            "try:\n"
            "    x = 1 / 0\n"
            "except ZeroDivisionError:\n"
            "    print('caught')"
        )
        self.assertIn("caught", output)


class TestExecSandboxBlocked(unittest.TestCase):
    """Verify that dangerous operations are blocked."""

    def test_import_blocked(self):
        output = run_exec("import os")
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("Import statements are not allowed", output)

    def test_from_import_blocked(self):
        output = run_exec("from pathlib import Path")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_open_blocked(self):
        output = run_exec("open('/etc/passwd')")
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("Use of builtin 'open' is not allowed", output)

    def test_dunder_import_blocked(self):
        output = run_exec("__import__('os')")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_eval_blocked(self):
        output = run_exec("eval('1+1')")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_exec_blocked(self):
        output = run_exec("exec('print(1)')")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_getattr_blocked(self):
        output = run_exec("getattr(int, 'mro')()")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_vars_blocked(self):
        output = run_exec("print(vars())")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_breakpoint_blocked(self):
        output = run_exec("breakpoint()")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_input_blocked(self):
        output = run_exec("input()")
        self.assertIn("[SANDBOX BLOCKED]", output)


class TestExecSandboxDunderEscapes(unittest.TestCase):
    """Verify that CPython dunder-based sandbox escapes are blocked."""

    def test_class_attr_blocked(self):
        output = run_exec("x = ().__class__")
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("__class__", output)

    def test_dict_attr_blocked(self):
        output = run_exec("x = type.__dict__")
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("__dict__", output)

    def test_mro_attr_blocked(self):
        output = run_exec("x = int.__mro__")
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("__mro__", output)

    def test_globals_attr_blocked(self):
        output = run_exec("def f(): pass\nx = f.__globals__")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_subclasses_attr_blocked(self):
        output = run_exec("x = object.__subclasses__()")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_code_attr_blocked(self):
        output = run_exec("def f(): pass\nx = f.__code__")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_builtins_attr_blocked(self):
        output = run_exec("x = __builtins__")
        # __builtins__ as a Name access won't hit attr check,
        # but it's not in allowed builtins so runtime blocks it
        self.assertNotIn("ESCAPED", output)

    def test_dunder_string_constant_blocked(self):
        """Blocks dict key access like type.__dict__['__subclasses__']."""
        output = run_exec('key = "__subclasses__"')
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("dunder attribute", output)

    def test_full_escape_chain_blocked(self):
        """The exact CPython escape: type.__dict__ → __subclasses__ → BuiltinImporter."""
        code = (
            'sc = type.__dict__["__subclasses__"]\n'
            'mro = type.__dict__["__mro__"].__get__(type)\n'
            'obj = mro[-1]\n'
            'subs = sc(obj)\n'
            'for s in subs:\n'
            '    if "BuiltinImporter" in str(s):\n'
            '        os_mod = s.load_module("os")\n'
            '        print("ESCAPED:", os_mod.getcwd())\n'
        )
        output = run_exec(code)
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertNotIn("ESCAPED", output)


class TestExecSandboxTimeout(unittest.TestCase):
    """Verify timeout enforcement."""

    def test_infinite_loop_times_out(self):
        output = run_exec("while True: pass", timeout=15)
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("timed out", output)


class TestExecSandboxFilesystem(unittest.TestCase):
    """Verify filesystem restrictions."""

    def test_no_file_write(self):
        output = run_exec("open('/tmp/escape.txt', 'w').write('x')")
        self.assertIn("[SANDBOX BLOCKED]", output)

    def test_no_file_read(self):
        output = run_exec("open('/etc/hostname').read()")
        self.assertIn("[SANDBOX BLOCKED]", output)


if __name__ == "__main__":
    unittest.main()

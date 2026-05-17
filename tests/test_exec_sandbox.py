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


class TestExecSandbox(unittest.TestCase):

    def test_print_works(self):
        output = run_exec("print('hello')")
        self.assertEqual(output.strip(), "hello")

    def test_import_blocked(self):
        output = run_exec("import os")
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("Import statements are not allowed", output)

    def test_open_blocked(self):
        output = run_exec("open('/etc/passwd')")
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("Use of builtin 'open' is not allowed", output)

    def test_dunder_blocked(self):
        output = run_exec("__import__('os')")
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("Use of builtin '__import__' is not allowed", output)

    def test_timeout(self):
        output = run_exec("while True: pass", timeout=15)
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("Execution timed out", output)

    def test_builtins_available(self):
        output = run_exec("print(len(range(3)))\nprint(sorted([3, 1, 2]))")
        self.assertIn("3", output)
        self.assertIn("[1, 2, 3]", output)

    def test_no_file_escape(self):
        output = run_exec("open('/tmp/escape.txt', 'w').write('x')")
        self.assertIn("[SANDBOX BLOCKED]", output)
        self.assertIn("Use of builtin 'open' is not allowed", output)


if __name__ == "__main__":
    unittest.main()

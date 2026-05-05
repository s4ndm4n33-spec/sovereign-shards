"""Tests for sandbox validation (app.agent.sandbox)."""

import os
import tempfile
import unittest

from app.agent.sandbox import (
    _check_syntax,
    _check_imports,
    _check_git_status,
    validate_before_push,
)


class TestSyntaxCheck(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, content):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_clean_file(self):
        self._write("good.py", "x = 1\n")
        result = _check_syntax(self.tmp)
        self.assertTrue(result.passed)

    def test_syntax_error(self):
        self._write("bad.py", "def broken(\n")
        result = _check_syntax(self.tmp)
        self.assertFalse(result.passed)
        self.assertIn("bad.py", result.details)


class TestImportCheck(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, content):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write(content)

    def test_parseable(self):
        self._write("ok.py", "import os\nprint('hello')\n")
        result = _check_imports(self.tmp)
        self.assertTrue(result.passed)

    def test_unparseable(self):
        self._write("bad.py", "def nope(:\n")
        result = _check_imports(self.tmp)
        self.assertFalse(result.passed)


class TestConflictCheck(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, content):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write(content)

    def test_no_conflicts(self):
        self._write("clean.py", "x = 1\n")
        result = _check_git_status(self.tmp)
        self.assertTrue(result.passed)

    def test_has_conflicts(self):
        content = "before\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> branch\nafter\n"
        self._write("conflict.py", content)
        result = _check_git_status(self.tmp)
        self.assertFalse(result.passed)


class TestFullSandbox(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "app"))
        with open(os.path.join(self.tmp, "app", "main.py"), "w") as f:
            f.write("print('hello')\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_project_passes(self):
        report = validate_before_push(
            self.tmp,
            copy_to_temp=True,
            skip_tests=True,
            skip_five_masters=True,
        )
        self.assertTrue(report.passed)

    def test_report_summary(self):
        report = validate_before_push(
            self.tmp,
            skip_tests=True,
            skip_five_masters=True,
        )
        summary = report.summary()
        self.assertIn("SANDBOX VALIDATION", summary)
        self.assertIn("SAFE TO PUSH", summary)


if __name__ == "__main__":
    unittest.main()

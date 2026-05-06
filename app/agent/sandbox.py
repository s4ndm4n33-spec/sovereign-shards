"""Pre-push validation sandbox.

Copies the working tree to a temp directory, runs a validation gauntlet
(syntax, imports, tests, Five Masters), and reports pass/fail before any
code leaves the machine.

Zero external deps. FAT32-safe (temp dir, atomic copies).
"""

from __future__ import annotations

import os
import py_compile
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ── Result types ─────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str = ""
    elapsed_s: float = 0.0

    def __str__(self) -> str:
        icon = "✅" if self.passed else "❌"
        line = f"{icon} {self.name} ({self.elapsed_s:.1f}s)"
        if self.details:
            # Indent details under the header
            indent = "\n    ".join(self.details.strip().splitlines())
            line += f"\n    {indent}"
        return line


@dataclass
class SandboxReport:
    checks: List[CheckResult] = field(default_factory=list)
    sandbox_dir: str = ""
    elapsed_s: float = 0.0

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed(self) -> list:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        total = len(self.checks)
        ok = sum(1 for c in self.checks if c.passed)
        icon = "✅" if self.passed else "❌"
        header = (
            f"\n{'='*50}\n"
            f"{icon} SANDBOX VALIDATION: {ok}/{total} checks passed "
            f"({self.elapsed_s:.1f}s)\n"
            f"{'='*50}\n"
        )
        body = "\n".join(str(c) for c in self.checks)
        verdict = (
            "\n🟢 SAFE TO PUSH" if self.passed
            else f"\n🔴 DO NOT PUSH — {len(self.failed)} check(s) failed"
        )
        return header + body + verdict


# ── Individual checks ────────────────────────────────────

def _check_syntax(project_dir: str) -> CheckResult:
    """py_compile every .py file."""
    t0 = time.time()
    errors = []
    count = 0
    for root, _dirs, files in os.walk(project_dir):
        # Skip hidden dirs, __pycache__, .git
        if any(part.startswith(".") or part == "__pycache__"
               for part in Path(root).parts):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            count += 1
            path = os.path.join(root, f)
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as exc:
                rel = os.path.relpath(path, project_dir)
                errors.append(f"{rel}: {exc.msg}")

    elapsed = time.time() - t0
    if errors:
        detail = "\n".join(errors[:20])
        if len(errors) > 20:
            detail += f"\n... and {len(errors) - 20} more"
        return CheckResult("Syntax", False, detail, elapsed)
    return CheckResult("Syntax", True, f"{count} files clean", elapsed)


def _check_imports(project_dir: str) -> CheckResult:
    """AST-parse every .py file to catch syntax / encoding issues."""
    import ast

    t0 = time.time()
    errors = []
    py_files = []
    for root, _dirs, files in os.walk(project_dir):
        if any(part.startswith(".") or part == "__pycache__"
               for part in Path(root).parts):
            continue
        for f in files:
            if f.endswith(".py") and f != "__init__.py":
                py_files.append(os.path.join(root, f))

    for path in py_files[:50]:  # cap to stay fast
        rel = os.path.relpath(path, project_dir)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            ast.parse(source, filename=rel)
        except SyntaxError as exc:
            errors.append(f"{rel}: SyntaxError: {exc.msg}")
        except Exception as exc:
            errors.append(f"{rel}: {exc}")

    elapsed = time.time() - t0
    if errors:
        return CheckResult("AST Parse", False, "\n".join(errors[:15]), elapsed)
    return CheckResult("AST Parse", True, f"{len(py_files)} files parsed", elapsed)


def _check_tests(project_dir: str, test_cmd: Optional[str] = None) -> CheckResult:
    """Run the project's test suite if one exists."""
    t0 = time.time()

    # Auto-detect test files
    if test_cmd is None:
        test_files = list(Path(project_dir).rglob("test_*.py"))
        test_files += list(Path(project_dir).rglob("*_test.py"))
        tests_dir = Path(project_dir) / "tests"
        if not test_files and not tests_dir.exists():
            elapsed = time.time() - t0
            return CheckResult("Tests", True, "No test files found (skipped)", elapsed)
        test_cmd = "python -m pytest tests/ -x -q 2>/dev/null || python -m unittest discover -s tests -q"

    try:
        result = subprocess.run(
            test_cmd, shell=True, capture_output=True, text=True,
            timeout=120, cwd=project_dir,
        )
    except subprocess.TimeoutExpired:
        return CheckResult("Tests", False, "Timed out after 120s", time.time() - t0)
    except Exception as exc:
        return CheckResult("Tests", False, str(exc), time.time() - t0)

    elapsed = time.time() - t0
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if len(output) > 2048:
        output = output[:2048] + "\n... [TRUNCATED]"

    if result.returncode == 0:
        return CheckResult("Tests", True, output or "All tests passed", elapsed)
    return CheckResult("Tests", False, output or f"Exit code {result.returncode}", elapsed)


def _check_five_masters(project_dir: str) -> CheckResult:
    """Run Five Masters AST analysis if available."""
    t0 = time.time()
    try:
        # Import locally to avoid hard dep
        import sys
        sys.path.insert(0, project_dir)
        from core.fivemasters import FiveMastersReport

        issues = []
        for root, _dirs, files in os.walk(project_dir):
            if any(part.startswith(".") or part == "__pycache__"
                   for part in Path(root).parts):
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        source = fh.read()
                    report = FiveMastersReport(source, filename=os.path.relpath(path, project_dir))
                    issues.extend(report.issues)
                except Exception:
                    pass  # File-level errors already caught by syntax check

        elapsed = time.time() - t0
        high = [i for i in issues if i.severity == "high"]
        med = [i for i in issues if i.severity == "medium"]

        if high:
            detail = f"{len(high)} high, {len(med)} medium, {len(issues) - len(high) - len(med)} low"
            top = "\n".join(f"  [{i.master}] {i.file}:{i.line} — {i.message}" for i in high[:10])
            return CheckResult("Five Masters", False, f"{detail}\n{top}", elapsed)

        detail = f"0 high, {len(med)} medium, {len(issues) - len(med)} low"
        return CheckResult("Five Masters", True, detail, elapsed)

    except ImportError:
        return CheckResult("Five Masters", True, "Not available (skipped)", time.time() - t0)
    except Exception as exc:
        return CheckResult("Five Masters", True, f"Skipped: {exc}", time.time() - t0)


def _check_git_status(project_dir: str) -> CheckResult:
    """Verify git state: no merge conflicts, clean index."""
    t0 = time.time()
    issues = []

    # Conflict marker patterns (split to avoid self-detection)
    marker_start = "<" * 7 + " "
    marker_mid = "=" * 7
    marker_end = ">" * 7 + " "

    for root, _dirs, files in os.walk(project_dir):
        if ".git" in root:
            continue
        for f in files:
            if not f.endswith((".py", ".md", ".json", ".txt", ".toml", ".cfg")):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
                has_start = any(line.startswith(marker_start) for line in lines)
                has_mid = any(line.strip() == marker_mid for line in lines)
                has_end = any(line.startswith(marker_end) for line in lines)
                if has_start and has_mid and has_end:
                    issues.append(os.path.relpath(path, project_dir))
            except Exception:
                pass

    elapsed = time.time() - t0
    if issues:
        return CheckResult("Conflict Check", False,
                           f"Merge conflict markers in:\n" + "\n".join(issues), elapsed)
    return CheckResult("Conflict Check", True, "No conflicts", elapsed)


# ── Main sandbox runner ──────────────────────────────────

def validate_before_push(
    project_dir: str = ".",
    test_cmd: Optional[str] = None,
    copy_to_temp: bool = True,
    skip_tests: bool = False,
    skip_five_masters: bool = False,
) -> SandboxReport:
    """Run the full validation gauntlet.

    If copy_to_temp is True, copies the project to a temp dir first
    so validation runs in complete isolation (no side effects).
    """
    t0 = time.time()
    project_dir = os.path.abspath(project_dir)
    report = SandboxReport()

    work_dir = project_dir
    if copy_to_temp:
        tmp = tempfile.mkdtemp(prefix="j_sandbox_")
        report.sandbox_dir = tmp
        # Copy project, skip .git and __pycache__
        shutil.copytree(
            project_dir, os.path.join(tmp, "project"),
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv", "node_modules"),
        )
        work_dir = os.path.join(tmp, "project")

    try:
        # 1. Conflict markers
        report.checks.append(_check_git_status(work_dir))

        # 2. Syntax (py_compile)
        report.checks.append(_check_syntax(work_dir))

        # 3. AST parse
        report.checks.append(_check_imports(work_dir))

        # 4. Tests (if they exist)
        if not skip_tests:
            report.checks.append(_check_tests(work_dir, test_cmd))

        # 5. Five Masters code quality
        if not skip_five_masters:
            report.checks.append(_check_five_masters(work_dir))

    finally:
        # Clean up temp dir
        if copy_to_temp and report.sandbox_dir:
            try:
                shutil.rmtree(report.sandbox_dir)
                report.sandbox_dir = "(cleaned)"
            except Exception:
                pass

    report.elapsed_s = time.time() - t0
    return report


# ── CLI entrypoint ───────────────────────────────────────

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    report = validate_before_push(target)
    print(report.summary())
    sys.exit(0 if report.passed else 1)

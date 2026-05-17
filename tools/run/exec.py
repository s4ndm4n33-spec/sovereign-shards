# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Sandboxed Python execution for J's run_exec tool.

Security layers:
  1. AST validation — block imports, dangerous builtins, ALL dunder attribute access
  2. Restricted builtins — only safe, pre-approved names available at runtime
  3. Subprocess isolation — code runs in a child process with temp cwd
  4. Timeout enforcement — configurable via J_EXEC_TIMEOUT (default 10s)
  5. Cleanup — temp directory removed on exit

Known attack surface closed:
  - type.__dict__["__subclasses__"] descriptor traversal (blocked by __dict__ AST rule)
  - BuiltinImporter.load_module escape chain (blocked by dunder + import rules)
  - __mro__ / __code__ / __closure__ introspection (blocked by blanket dunder rule)
"""

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

# ── Security configuration ───────────────────────────────────────────

BLOCKED_BUILTINS = {
    "__import__",
    "open",
    "eval",
    "exec",
    "compile",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "vars",
    "dir",
    "breakpoint",
    "input",
    "memoryview",
    "classmethod",
    "staticmethod",
    "property",
    "super",
    "object",
}

ALLOWED_BUILTINS = {
    "print",
    "len",
    "range",
    "int",
    "str",
    "float",
    "list",
    "dict",
    "set",
    "tuple",
    "bool",
    "enumerate",
    "zip",
    "map",
    "filter",
    "sorted",
    "min",
    "max",
    "sum",
    "abs",
    "round",
    "type",
    "isinstance",
    "hasattr",
    "repr",
    "chr",
    "ord",
    "hex",
    "bin",
    "oct",
    "any",
    "all",
    "reversed",
    "slice",
    "format",
    "hash",
    "id",
    "callable",
    "iter",
    "next",
    "pow",
    "divmod",
    "True",
    "False",
    "None",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "StopIteration",
    "ZeroDivisionError",
    "RuntimeError",
    "Exception",
    "ArithmeticError",
}

RESTRICTED_MODULES = frozenset((
    "socket", "requests", "urllib", "http", "ftplib", "smtplib",
    "subprocess", "os", "sys", "shutil", "pathlib", "glob",
    "ctypes", "multiprocessing", "threading", "signal",
    "importlib", "pkgutil", "code", "codeop", "compileall",
    "webbrowser", "antigravity", "turtle",
))

# Regex: any attribute that starts and ends with double underscore
_DUNDER_RE = re.compile(r"^__.*__$")


# ── AST validation ───────────────────────────────────────────────────

def _reject(message: str) -> None:
    print(f"[SANDBOX BLOCKED] {message}")


def _validate_ast(tree: ast.AST) -> None:
    """Walk the AST and reject dangerous patterns."""
    for node in ast.walk(tree):
        # Block ALL import statements
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                names = ", ".join(a.name for a in node.names)
            else:
                names = node.module or ""
            raise ValueError(f"Import statements are not allowed (tried to import '{names}')")

        # Block calls to dangerous builtins
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_BUILTINS:
                raise ValueError(f"Use of builtin '{node.func.id}' is not allowed")

        # Block ALL dunder attribute access (catches __dict__, __class__,
        # __mro__, __subclasses__, __globals__, __code__, __init__, etc.)
        if isinstance(node, ast.Attribute):
            if _DUNDER_RE.match(node.attr):
                raise ValueError(f"Access to dunder attribute '{node.attr}' is not allowed")

        # Block string constants that look like dunder names used as dict keys
        # Catches: type.__dict__["__subclasses__"] via Constant node in Subscript
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _DUNDER_RE.match(node.value):
                raise ValueError(
                    f"String literal '{node.value}' resembles a dunder attribute and is not "
                    f"allowed in sandboxed code"
                )


# ── Sandbox subprocess builder ───────────────────────────────────────

def _build_sandbox_code() -> str:
    """Build the restricted-builtins wrapper that the subprocess executes."""
    allowed_defs = []
    for name in sorted(ALLOWED_BUILTINS):
        allowed_defs.append(f'"{name}": getattr(builtins, "{name}", None)')
    allowed = ", ".join(allowed_defs)
    return (
        "import builtins, sys\n"
        f"safe = {{{allowed}}}\n"
        "globals_dict = {'__builtins__': safe}\n"
        "code = sys.stdin.read()\n"
        "exec(compile(code, '<exec>', 'exec'), globals_dict)\n"
    )


# ── Main execution ──────────────────────────────────────────────────

code = sys.stdin.read()

# Phase 1: AST validation
try:
    tree = ast.parse(code, filename="<exec>")
    _validate_ast(tree)
except SyntaxError as error:
    print(f"[EXEC ERROR] {error}")
    sys.exit(0)
except ValueError as error:
    _reject(str(error))
    sys.exit(0)

# Phase 2: Execute in sandboxed subprocess
sandbox_dir = tempfile.mkdtemp()
try:
    timeout = int(os.getenv("J_EXEC_TIMEOUT", "10"))

    # Strip dangerous env vars from child process
    clean_env = {
        k: v for k, v in os.environ.items()
        if k in ("PATH", "HOME", "LANG", "TERM", "J_EXEC_TIMEOUT")
    }

    result = subprocess.run(
        [sys.executable, "-c", _build_sandbox_code()],
        input=code,
        capture_output=True,
        text=True,
        cwd=sandbox_dir,
        env=clean_env,
        timeout=timeout,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
except subprocess.TimeoutExpired:
    _reject(f"Execution timed out after {timeout} seconds")
except Exception as error:
    print(f"[EXEC ERROR] {error}")
finally:
    shutil.rmtree(sandbox_dir, ignore_errors=True)
    # Future: impose Linux memory limits with resource.setrlimit().

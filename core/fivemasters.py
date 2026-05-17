# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Five Masters Code Governance — AST-based analysis.

Each Master evaluates a specific quality dimension using real AST parsing.
Falls back to heuristic analysis for non-parseable code.

Masters:
  Korotkevich — Efficiency: detect wasteful patterns
  Torvalds    — Error Handling: catch unsafe exception patterns
  Carmack     — Performance: spot structural anti-patterns
  Hamilton    — Fault Tolerance: verify defensive coding
  Ritchie     — Clarity: enforce naming and structure conventions
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class Issue:
    """A single quality issue found by a Master."""
    master: str
    line: int
    message: str
    severity: str = "warning"  # "warning" | "error"


@dataclass
class FiveMastersReport:
    korotkevich: bool
    torvalds: bool
    carmack: bool
    hamilton: bool
    ritchie: bool
    issues: list[Issue] = field(default_factory=list)

    def score(self) -> int:
        return sum([
            self.korotkevich,
            self.torvalds,
            self.carmack,
            self.hamilton,
            self.ritchie,
        ])

    def summary(self) -> str:
        """Human-readable summary."""
        names = {
            "korotkevich": ("Efficiency", self.korotkevich),
            "torvalds": ("Error Handling", self.torvalds),
            "carmack": ("Performance", self.carmack),
            "hamilton": ("Fault Tolerance", self.hamilton),
            "ritchie": ("Clarity", self.ritchie),
        }
        lines = [f"Five Masters: {self.score()}/5"]
        for key, (label, passed) in names.items():
            icon = "✓" if passed else "✗"
            lines.append(f"  {icon} {label} ({key})")
        if self.issues:
            lines.append(f"\n  {len(self.issues)} issue(s):")
            for iss in self.issues[:15]:  # cap display
                lines.append(f"    L{iss.line}: [{iss.master}] {iss.message}")
            if len(self.issues) > 15:
                lines.append(f"    ... and {len(self.issues) - 15} more")
        return "\n".join(lines)


# ── AST Visitors ──────────────────────────────────────────────────────


class _KorotkevichVisitor(ast.NodeVisitor):
    """Efficiency: detect wasteful patterns."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def visit_For(self, node: ast.For) -> None:
        # Detect `for i in range(len(x))` — should be enumerate
        if (isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "range"
                and len(node.iter.args) == 1):
            arg = node.iter.args[0]
            if (isinstance(arg, ast.Call)
                    and isinstance(arg.func, ast.Name)
                    and arg.func.id == "len"):
                self.issues.append(Issue(
                    "korotkevich", node.lineno,
                    "for i in range(len(x)) — use enumerate() or iterate directly"))

        # Detect nested for loops (3+ depth) — potential O(n³)
        for child in ast.walk(node):
            if child is not node and isinstance(child, ast.For):
                for grandchild in ast.walk(child):
                    if grandchild is not child and isinstance(grandchild, ast.For):
                        self.issues.append(Issue(
                            "korotkevich", node.lineno,
                            "Triple-nested loop detected — review for O(n³) complexity",
                            severity="error"))
                        break
                break

        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        # Detect string concatenation in a loop (+=)
        # This is checked at the AugAssign level instead
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # Detect str += str inside a loop body
        if isinstance(node.op, ast.Add):
            # We can't always tell if it's a string, but flag the pattern
            pass  # Would need type inference — skip for now
        self.generic_visit(node)


class _TorvaldsVisitor(ast.NodeVisitor):
    """Error Handling: detect unsafe exception patterns."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Bare `except:` with no type
        if node.type is None:
            self.issues.append(Issue(
                "torvalds", node.lineno,
                "Bare except: — catches KeyboardInterrupt and SystemExit"))

        # `except Exception` without logging/re-raise
        if (node.type and isinstance(node.type, ast.Name)
                and node.type.id == "Exception"):
            body_has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(node))
            body_has_log = False
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                    if n.func.attr in ("error", "warning", "exception", "critical"):
                        body_has_log = True
                        break
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                    if n.func.id == "print":
                        body_has_log = True
                        break
            if not body_has_raise and not body_has_log:
                self.issues.append(Issue(
                    "torvalds", node.lineno,
                    "except Exception without re-raise or logging — errors silenced"))

        # `except: pass` — the worst pattern
        if (node.type is None
                and len(node.body) == 1
                and isinstance(node.body[0], ast.Pass)):
            self.issues.append(Issue(
                "torvalds", node.lineno,
                "except: pass — silently swallows all errors",
                severity="error"))

        self.generic_visit(node)


class _CarmackVisitor(ast.NodeVisitor):
    """Performance: detect structural anti-patterns."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Mutable default arguments
        for default in node.args.defaults + node.args.kw_defaults:
            if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.issues.append(Issue(
                    "carmack", node.lineno,
                    f"Mutable default arg in {node.name}() — shared across calls"))

        # Excessive nesting depth (>4 levels inside function)
        max_depth = _max_nesting_depth(node, 0)
        if max_depth > 4:
            self.issues.append(Issue(
                "carmack", node.lineno,
                f"{node.name}() has {max_depth} nesting levels — consider refactoring"))

        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Global(self, node: ast.Global) -> None:
        self.issues.append(Issue(
            "carmack", node.lineno,
            f"global {', '.join(node.names)} — prefer parameter passing"))
        self.generic_visit(node)


class _HamiltonVisitor(ast.NodeVisitor):
    """Fault Tolerance: verify defensive coding."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []
        self._has_any_try = False
        self._file_ops: list[int] = []

    def visit_Try(self, node: ast.Try) -> None:
        self._has_any_try = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Track file/network operations that should be guarded
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            self._file_ops.append(node.lineno)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("urlopen", "connect", "send", "recv"):
                self._file_ops.append(node.lineno)
        self.generic_visit(node)

    def finalize(self, tree: ast.Module) -> None:
        """Check post-walk conditions."""
        # Check if file/network ops are inside try blocks
        try_ranges: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                end = max(
                    (getattr(n, "lineno", node.lineno) for n in ast.walk(node)),
                    default=node.lineno,
                )
                try_ranges.append((node.lineno, end))

        for op_line in self._file_ops:
            guarded = any(start <= op_line <= end for start, end in try_ranges)
            if not guarded:
                self.issues.append(Issue(
                    "hamilton", op_line,
                    "I/O operation without try/except guard"))


class _RitchieVisitor(ast.NodeVisitor):
    """Clarity: naming conventions and structure."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Function too long (>60 lines)
        if node.end_lineno and node.lineno:
            length = node.end_lineno - node.lineno
            if length > 60:
                self.issues.append(Issue(
                    "ritchie", node.lineno,
                    f"{node.name}() is {length} lines — consider splitting"))

        # Non-snake_case function name (skip dunder and private)
        if not node.name.startswith("_"):
            if node.name != node.name.lower() and "_" not in node.name:
                # camelCase or PascalCase function
                if not node.name.isupper():  # allow ALL_CAPS constants
                    self.issues.append(Issue(
                        "ritchie", node.lineno,
                        f"{node.name}() — use snake_case for functions"))

        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # Class should be PascalCase
        if node.name[0].islower() and "_" in node.name:
            self.issues.append(Issue(
                "ritchie", node.lineno,
                f"class {node.name} — use PascalCase for classes"))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # Magic numbers (int/float literals > 1 that aren't 0, 1, 2, or common)
        if isinstance(node.value, (int, float)):
            if isinstance(node.value, bool):
                return
            if node.value not in (0, 1, 2, -1, 0.0, 1.0, 0.5, 100, 1000, 1024):
                # Only flag if it's a bare constant in assignment/comparison
                # Can't easily check context without parent — skip for now
                pass
        self.generic_visit(node)


# ── Helpers ───────────────────────────────────────────────────────────


def _max_nesting_depth(node: ast.AST, current: int) -> int:
    """Compute max nesting depth of control flow inside a node."""
    max_d = current
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.With,
                              ast.Try, ast.AsyncFor, ast.AsyncWith)):
            d = _max_nesting_depth(child, current + 1)
            max_d = max(max_d, d)
        else:
            d = _max_nesting_depth(child, current)
            max_d = max(max_d, d)
    return max_d


# ── Public API ────────────────────────────────────────────────────────


def evaluate_code(code: str) -> FiveMastersReport:
    """Run all Five Masters against a code string.

    Uses AST parsing for real analysis. Falls back to heuristics
    if the code can't be parsed (e.g., code fragments).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return _evaluate_heuristic(code)

    all_issues: list[Issue] = []

    # Korotkevich — Efficiency
    k = _KorotkevichVisitor()
    k.visit(tree)
    all_issues.extend(k.issues)

    # Torvalds — Error Handling
    t = _TorvaldsVisitor()
    t.visit(tree)
    all_issues.extend(t.issues)

    # Carmack — Performance
    c = _CarmackVisitor()
    c.visit(tree)
    all_issues.extend(c.issues)

    # Hamilton — Fault Tolerance
    h = _HamiltonVisitor()
    h.visit(tree)
    h.finalize(tree)
    all_issues.extend(h.issues)

    # Ritchie — Clarity
    r = _RitchieVisitor()
    r.visit(tree)
    all_issues.extend(r.issues)

    def _master_pass(name: str) -> bool:
        errors = [i for i in all_issues if i.master == name and i.severity == "error"]
        warnings = [i for i in all_issues if i.master == name and i.severity == "warning"]
        return len(errors) == 0 and len(warnings) <= 2

    return FiveMastersReport(
        korotkevich=_master_pass("korotkevich"),
        torvalds=_master_pass("torvalds"),
        carmack=_master_pass("carmack"),
        hamilton=_master_pass("hamilton"),
        ritchie=_master_pass("ritchie"),
        issues=all_issues,
    )


def _evaluate_heuristic(code: str) -> FiveMastersReport:
    """Fallback heuristic analysis for unparseable code fragments."""
    issues: list[Issue] = []

    if "for i in range(len" in code:
        issues.append(Issue("korotkevich", 0, "range(len()) — use enumerate()"))
    if "except:" in code and "except:" in code.replace("except: ", ""):
        issues.append(Issue("torvalds", 0, "Bare except: detected"))
    if "global " in code:
        issues.append(Issue("carmack", 0, "Global variable usage"))

    return FiveMastersReport(
        korotkevich="for i in range(len" not in code,
        torvalds="except:" not in code,
        carmack="global " not in code.lower() or "def " in code,
        hamilton="try:" in code or "raise " in code,
        ritchie=True,  # can't check naming without AST
        issues=issues,
    )

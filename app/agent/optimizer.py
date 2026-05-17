# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Five Masters Code Optimizer — the transformation pipeline.

Accepts Python source code, analyses it against the Five Masters,
applies deterministic AST transformations, optionally invokes the
LLM for semantic fixes, and verifies the result through the sandbox.

Five stages: INPUT → ANALYSIS → PLAN → TRANSFORM → VERIFY

Zero external deps. Local first. Sovereign.
"""

from __future__ import annotations

import ast
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Internal imports — all within the sovereign-shards codebase
# These are relative to the project root on the shard
import sys
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.fivemasters import evaluate_code, FiveMastersReport, Issue
from app.agent.transforms import (
    apply_all_deterministic,
    TransformResult,
)


# ── Data Structures ──────────────────────────────────────────────────


@dataclass
class FixPlan:
    """A planned fix for a single issue."""
    issue: Issue
    strategy: str          # "deterministic" | "semantic" | "skip"
    reason: str            # Why this strategy was chosen
    estimated_lines: int   # Lines affected


@dataclass
class OptimizeResult:
    """Complete result of an optimization run."""
    file_path: str
    original_source: str
    optimized_source: str
    before_report: FiveMastersReport
    after_report: FiveMastersReport
    transforms_applied: list[TransformResult] = field(default_factory=list)
    transforms_skipped: list[TransformResult] = field(default_factory=list)
    semantic_fixes: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    reverted: bool = False
    revert_reason: str = ""

    @property
    def improved(self) -> bool:
        return self.after_report.score() >= self.before_report.score()

    @property
    def score_delta(self) -> int:
        return self.after_report.score() - self.before_report.score()

    @property
    def issues_fixed(self) -> int:
        return len(self.before_report.issues) - len(self.after_report.issues)

    def summary(self) -> str:
        """Human-readable optimization report."""
        lines = [
            "═" * 62,
            "  Five Masters Code Optimizer — Report",
            "═" * 62,
            f"  File: {self.file_path}",
            f"  Before: {self.before_report.score()}/5 Masters"
            f"  │  After: {self.after_report.score()}/5 Masters",
            f"  Time: {self.elapsed_s:.2f}s",
            "",
        ]

        if self.reverted:
            lines.append(f"  ⚠ REVERTED: {self.revert_reason}")
            lines.append("")
            lines.append("  Original source returned unchanged.")
            lines.append("═" * 62)
            return "\n".join(lines)

        applied = [t for t in self.transforms_applied if t.applied]
        skipped = [t for t in self.transforms_applied if not t.applied]
        skipped += self.transforms_skipped

        if applied:
            lines.append(f"  Fixes Applied: {len(applied)}")
            for t in applied:
                lines.append(
                    f"  ├─ [{t.master.capitalize()}] L{t.line}: {t.description}")
            lines.append("")

        if skipped:
            lines.append(f"  Skipped: {len(skipped)}")
            for t in skipped:
                lines.append(
                    f"  └─ [{t.master.capitalize()}] L{t.line}: {t.description}")
            lines.append("")

        if self.semantic_fixes:
            lines.append(f"  Semantic Fixes: {len(self.semantic_fixes)}")
            for sf in self.semantic_fixes:
                lines.append(f"  ├─ {sf}")
            lines.append("")

        # Before/after issue counts per master
        lines.append("  Master Breakdown:")
        masters = ["korotkevich", "torvalds", "carmack", "hamilton", "ritchie"]
        labels = ["Efficiency", "Error Handling", "Performance",
                  "Fault Tolerance", "Clarity"]
        for m, label in zip(masters, labels):
            before_n = len([i for i in self.before_report.issues if i.master == m])
            after_n = len([i for i in self.after_report.issues if i.master == m])
            before_pass = getattr(self.before_report, m)
            after_pass = getattr(self.after_report, m)
            b_icon = "✓" if before_pass else "✗"
            a_icon = "✓" if after_pass else "✗"
            delta = before_n - after_n
            delta_str = f"(-{delta})" if delta > 0 else "(+{abs(delta)})" if delta < 0 else "(=)"
            lines.append(
                f"    {b_icon}→{a_icon} {label}: "
                f"{before_n}→{after_n} issues {delta_str}")

        lines.append("")
        lines.append("═" * 62)
        return "\n".join(lines)

    def diff(self) -> str:
        """Generate a unified diff between original and optimized."""
        import difflib
        return "\n".join(difflib.unified_diff(
            self.original_source.splitlines(),
            self.optimized_source.splitlines(),
            fromfile=f"a/{self.file_path}",
            tofile=f"b/{self.file_path}",
            lineterm="",
        ))


# ── Stage 1: INPUT ───────────────────────────────────────────────────


def _read_source(file_path: str) -> str:
    """Read source from a file path."""
    return Path(file_path).read_text(encoding="utf-8", errors="replace")


# ── Stage 2: ANALYSIS ────────────────────────────────────────────────


def _analyse(source: str) -> tuple[ast.Module, FiveMastersReport]:
    """Parse and evaluate source against Five Masters."""
    tree = ast.parse(source)
    report = evaluate_code(source)
    return tree, report


# ── Stage 3: PLAN ────────────────────────────────────────────────────


# Issues that can be fixed deterministically (by master + message pattern)
_DETERMINISTIC_PATTERNS = {
    "korotkevich": ["range(len"],
    "torvalds": ["Bare except", "except Exception without"],
    "carmack": ["Mutable default arg", "global "],
    "hamilton": ["I/O operation without"],
}

# Issues that need the LLM
_SEMANTIC_PATTERNS = {
    "ritchie": ["lines — consider splitting"],
    "carmack": ["nesting levels — consider refactoring"],
}


def _classify_issue(issue: Issue) -> str:
    """Classify an issue as deterministic, semantic, or skip."""
    for master, patterns in _DETERMINISTIC_PATTERNS.items():
        if issue.master == master:
            for pat in patterns:
                if pat in issue.message:
                    return "deterministic"

    for master, patterns in _SEMANTIC_PATTERNS.items():
        if issue.master == master:
            for pat in patterns:
                if pat in issue.message:
                    return "semantic"

    # Default: deterministic fixes handle most patterns,
    # anything unknown is flagged but skipped
    return "skip"


def _build_plan(report: FiveMastersReport) -> list[FixPlan]:
    """Build an ordered fix plan from a Five Masters report."""
    plans = []

    # Sort: errors first, then by line
    sorted_issues = sorted(
        report.issues,
        key=lambda i: (0 if i.severity == "error" else 1, i.line),
    )

    for issue in sorted_issues:
        strategy = _classify_issue(issue)
        plans.append(FixPlan(
            issue=issue,
            strategy=strategy,
            reason=f"{'AST transform' if strategy == 'deterministic' else 'needs model' if strategy == 'semantic' else 'no auto-fix available'}",
            estimated_lines=5,
        ))

    return plans


# ── Stage 4: TRANSFORM ──────────────────────────────────────────────


def _apply_deterministic(tree: ast.Module) -> tuple[ast.Module, list[TransformResult]]:
    """Apply all deterministic AST transformations."""
    return apply_all_deterministic(tree)


def _apply_semantic(
    source: str,
    issues: list[Issue],
    llm_fn=None,
) -> tuple[str, list[str]]:
    """Apply semantic fixes using the LLM.

    Args:
        source: Current source code after deterministic fixes.
        issues: Semantic issues to address.
        llm_fn: Optional callable(prompt) -> str. If None, semantic
                fixes are skipped (--no-model mode).

    Returns:
        (modified_source, list of fix descriptions)
    """
    if not llm_fn or not issues:
        return source, []

    fixes_applied = []
    current = source

    for issue in issues:
        # Extract the affected function/block
        block, start, end = _extract_block(current, issue.line)
        if not block:
            continue

        prompt = (
            f"You are refactoring a single Python function. The Five Masters "
            f"identified this issue:\n"
            f"  [{issue.master}] Line {issue.line}: {issue.message}\n\n"
            f"Here is the function:\n```python\n{block}\n```\n\n"
            f"Rewrite ONLY this function. Preserve exact behaviour. "
            f"Return only the Python code, no explanation."
        )

        try:
            rewritten = llm_fn(prompt)
            if not rewritten:
                continue

            # Strip markdown fences if model added them
            rewritten = rewritten.strip()
            if rewritten.startswith("```"):
                lines = rewritten.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                rewritten = "\n".join(lines)

            # Validate the rewrite parses
            ast.parse(rewritten)

            # Splice it back into the source
            source_lines = current.split("\n")
            new_lines = (source_lines[:start]
                        + rewritten.split("\n")
                        + source_lines[end:])
            candidate = "\n".join(new_lines)

            # Validate the whole file still parses
            ast.parse(candidate)
            current = candidate
            fixes_applied.append(
                f"[{issue.master}] L{issue.line}: {issue.message} — rewritten")
        except (SyntaxError, Exception):
            # If anything fails, skip this fix
            continue

    return current, fixes_applied


def _extract_block(source: str, target_line: int) -> tuple[str, int, int]:
    """Extract the function/class containing the target line.

    Returns (block_source, start_line_idx, end_line_idx) or ("", 0, 0).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "", 0, 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.lineno <= target_line
                    and node.end_lineno
                    and node.end_lineno >= target_line):
                lines = source.split("\n")
                start = node.lineno - 1  # 0-indexed
                end = node.end_lineno     # exclusive
                block = "\n".join(lines[start:end])
                return block, start, end

    return "", 0, 0


# ── Stage 5: VERIFY ─────────────────────────────────────────────────


def _verify(
    original_source: str,
    optimized_source: str,
    before: FiveMastersReport,
) -> tuple[bool, str, FiveMastersReport]:
    """Verify the optimized source.

    Returns (passed, reason, after_report).
    """
    # Must still parse
    try:
        ast.parse(optimized_source)
    except SyntaxError as e:
        empty = FiveMastersReport(False, False, False, False, False, [])
        return False, f"Optimized source has syntax error: {e}", empty

    # Five Masters score must not decrease
    after = evaluate_code(optimized_source)
    if after.score() < before.score():
        return False, (
            f"Score decreased: {before.score()}/5 → {after.score()}/5"
        ), after

    # No new errors
    before_errors = {(i.master, i.message) for i in before.issues
                     if i.severity == "error"}
    after_errors = {(i.master, i.message) for i in after.issues
                    if i.severity == "error"}
    new_errors = after_errors - before_errors
    if new_errors:
        msgs = [f"[{m}] {msg}" for m, msg in new_errors]
        return False, f"New errors introduced: {'; '.join(msgs)}", after

    return True, "passed", after


# ── Main Pipeline ────────────────────────────────────────────────────


def optimize_file(
    file_path: str,
    dry_run: bool = False,
    use_model: bool = False,
    llm_fn=None,
) -> OptimizeResult:
    """Optimize a single Python file.

    Args:
        file_path: Path to the .py file.
        dry_run: If True, report issues without applying fixes.
        use_model: If True and llm_fn is provided, apply semantic fixes.
        llm_fn: Optional callable(prompt) -> str for semantic fixes.

    Returns:
        OptimizeResult with full before/after analysis.
    """
    start = time.monotonic()
    source = _read_source(file_path)
    rel_path = os.path.basename(file_path)

    # Stage 2: ANALYSIS
    try:
        tree, before = _analyse(source)
    except SyntaxError as e:
        elapsed = time.monotonic() - start
        return OptimizeResult(
            file_path=rel_path,
            original_source=source,
            optimized_source=source,
            before_report=FiveMastersReport(False, False, False, False, False, []),
            after_report=FiveMastersReport(False, False, False, False, False, []),
            elapsed_s=elapsed,
            reverted=True,
            revert_reason=f"Syntax error — cannot optimise: {e}",
        )

    # If already 5/5 with no issues, nothing to do
    if before.score() == 5 and not before.issues:
        elapsed = time.monotonic() - start
        return OptimizeResult(
            file_path=rel_path,
            original_source=source,
            optimized_source=source,
            before_report=before,
            after_report=before,
            elapsed_s=elapsed,
        )

    # Stage 3: PLAN
    plan = _build_plan(before)
    semantic_issues = [p.issue for p in plan if p.strategy == "semantic"]
    skipped = [TransformResult(
        applied=False,
        description=f"{p.issue.message} — {p.reason}",
        master=p.issue.master,
        line=p.issue.line,
    ) for p in plan if p.strategy == "skip"]

    if dry_run:
        elapsed = time.monotonic() - start
        return OptimizeResult(
            file_path=rel_path,
            original_source=source,
            optimized_source=source,
            before_report=before,
            after_report=before,
            transforms_skipped=skipped + [TransformResult(
                applied=False,
                description=f"{p.issue.message} — dry run",
                master=p.issue.master,
                line=p.issue.line,
            ) for p in plan if p.strategy == "deterministic"],
            elapsed_s=elapsed,
        )

    # Stage 4: TRANSFORM — deterministic
    new_tree, det_results = _apply_deterministic(tree)
    optimized = ast.unparse(new_tree)

    # Stage 4b: TRANSFORM — semantic (optional)
    sem_descriptions = []
    if use_model and llm_fn and semantic_issues:
        optimized, sem_descriptions = _apply_semantic(
            optimized, semantic_issues, llm_fn)

    # Stage 5: VERIFY
    passed, reason, after = _verify(source, optimized, before)
    elapsed = time.monotonic() - start

    if not passed:
        return OptimizeResult(
            file_path=rel_path,
            original_source=source,
            optimized_source=source,  # revert
            before_report=before,
            after_report=before,
            transforms_applied=det_results,
            transforms_skipped=skipped,
            semantic_fixes=sem_descriptions,
            elapsed_s=elapsed,
            reverted=True,
            revert_reason=reason,
        )

    return OptimizeResult(
        file_path=rel_path,
        original_source=source,
        optimized_source=optimized,
        before_report=before,
        after_report=after,
        transforms_applied=det_results,
        transforms_skipped=skipped,
        semantic_fixes=sem_descriptions,
        elapsed_s=elapsed,
    )


def optimize_directory(
    dir_path: str,
    dry_run: bool = False,
    use_model: bool = False,
    llm_fn=None,
) -> list[OptimizeResult]:
    """Optimize all .py files in a directory.

    Returns a list of OptimizeResult, one per file.
    """
    results = []
    dir_path = os.path.abspath(dir_path)
    skip = {"__pycache__", ".git", ".venv", "venv", "node_modules",
            "models", "model-server"}

    for dirpath, dirnames, filenames in os.walk(dir_path):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fname in sorted(filenames):
            if not fname.endswith(".py"):
                continue
            full = os.path.join(dirpath, fname)
            result = optimize_file(full, dry_run=dry_run,
                                   use_model=use_model, llm_fn=llm_fn)
            results.append(result)

    return results


def batch_summary(results: list[OptimizeResult]) -> str:
    """Summarise a batch optimization run."""
    total = len(results)
    improved = sum(1 for r in results if r.score_delta > 0)
    perfect = sum(1 for r in results
                  if r.after_report.score() == 5 and not r.after_report.issues)
    reverted = sum(1 for r in results if r.reverted)
    total_fixes = sum(len([t for t in r.transforms_applied if t.applied])
                      for r in results)
    total_time = sum(r.elapsed_s for r in results)

    lines = [
        "═" * 62,
        "  Five Masters Code Optimizer — Batch Summary",
        "═" * 62,
        f"  Files scanned:   {total}",
        f"  Files improved:  {improved}",
        f"  Files at 5/5:    {perfect}",
        f"  Files reverted:  {reverted}",
        f"  Total fixes:     {total_fixes}",
        f"  Total time:      {total_time:.2f}s",
        "",
    ]

    # Per-file summary
    for r in results:
        if r.score_delta > 0 or r.reverted:
            icon = "⚠" if r.reverted else "✓"
            lines.append(
                f"  {icon} {r.file_path}: "
                f"{r.before_report.score()}→{r.after_report.score()}/5"
                f" ({len([t for t in r.transforms_applied if t.applied])} fixes)")

    lines.append("")
    lines.append("═" * 62)
    return "\n".join(lines)


# ── CLI Entry Point ──────────────────────────────────────────────────


def main() -> None:
    """CLI entry point for the optimizer.

    Usage:
        python -m app.agent.optimizer path/to/file.py [--dry-run] [--diff]
        python -m app.agent.optimizer path/to/dir/ [--dry-run]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Five Masters Code Optimizer")
    parser.add_argument("path", help="File or directory to optimize")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report issues without applying fixes")
    parser.add_argument("--diff", action="store_true",
                        help="Show unified diff of changes")
    parser.add_argument("--no-model", action="store_true",
                        help="Deterministic fixes only (no LLM)")
    args = parser.parse_args()

    target = os.path.abspath(args.path)

    if os.path.isfile(target):
        result = optimize_file(
            target,
            dry_run=args.dry_run,
            use_model=not args.no_model,
        )
        print(result.summary())
        if args.diff and not result.reverted:
            print()
            print(result.diff())
        if not args.dry_run and not result.reverted:
            if result.optimized_source != result.original_source:
                Path(target).write_text(result.optimized_source,
                                        encoding="utf-8")
                print(f"\n  ✓ Written to {target}")

    elif os.path.isdir(target):
        results = optimize_directory(
            target,
            dry_run=args.dry_run,
            use_model=not args.no_model,
        )
        print(batch_summary(results))
        if not args.dry_run:
            for r in results:
                if (not r.reverted
                        and r.optimized_source != r.original_source):
                    full = os.path.join(target, r.file_path)
                    if os.path.isfile(full):
                        Path(full).write_text(r.optimized_source,
                                              encoding="utf-8")
    else:
        print(f"Error: {target} not found")
        sys.exit(1)


if __name__ == "__main__":
    main()

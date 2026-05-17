# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Codebase statistics: lines of code, functions/classes, TODOs.

Usage:
    python stats.py loc              — lines of code per module + total
    python stats.py funcs [path]     — list every def/class with file:line
    python stats.py todos            — find TODO/FIXME/HACK comments
    python stats.py summary          — combined overview

Stdlib only. No dependencies.
"""

import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SKIP_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules", "logs", "memory"}
PY_EXT = ".py"


def _py_files(root: Path | None = None) -> list[Path]:
    """Walk project tree, yield .py files, skip noise directories."""
    start = root or BASE_DIR
    if start.is_file():
        return [start] if start.suffix == PY_EXT else []
    result: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(start):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in sorted(filenames):
            if fname.endswith(PY_EXT):
                result.append(Path(dirpath) / fname)
    return result


# ── loc ──────────────────────────────────────────────────────────────

def cmd_loc(root: Path | None = None) -> tuple[list[tuple[str, int]], int]:
    """Lines of code per file, sorted descending. Returns (rows, total)."""
    rows: list[tuple[str, int]] = []
    for fp in _py_files(root):
        try:
            count = sum(1 for _ in open(fp, encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        rel = str(fp.relative_to(BASE_DIR)).replace("\\", "/")
        rows.append((rel, count))
    rows.sort(key=lambda r: r[1], reverse=True)
    total = sum(c for _, c in rows)
    return rows, total


def print_loc(root: Path | None = None) -> None:
    rows, total = cmd_loc(root)
    print(f"{'File':<50} {'Lines':>6}")
    print("-" * 57)
    for rel, count in rows:
        print(f"{rel:<50} {count:>6}")
    print("-" * 57)
    print(f"{'TOTAL':<50} {total:>6}")
    print(f"\n{len(rows)} files, {total} lines of Python")


# ── funcs ────────────────────────────────────────────────────────────

DEF_RE = re.compile(r"^\s*(def |class )\s*(\w+)")


def cmd_funcs(root: Path | None = None) -> list[tuple[str, int, str, str]]:
    """Return (relpath, lineno, kind, name) for every def/class."""
    hits: list[tuple[str, int, str, str]] = []
    for fp in _py_files(root):
        rel = str(fp.relative_to(BASE_DIR)).replace("\\", "/")
        try:
            lines = open(fp, encoding="utf-8", errors="ignore").readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            m = DEF_RE.match(line)
            if m:
                kind = "def" if m.group(1).strip() == "def" else "class"
                hits.append((rel, i, kind, m.group(2)))
    return hits


def print_funcs(root: Path | None = None) -> None:
    hits = cmd_funcs(root)
    n_def = sum(1 for h in hits if h[2] == "def")
    n_cls = sum(1 for h in hits if h[2] == "class")
    print(f"{'File':<45} {'Line':>5}  {'Kind':<6} Name")
    print("-" * 75)
    for rel, lineno, kind, name in hits:
        print(f"{rel:<45} {lineno:>5}  {kind:<6} {name}")
    print("-" * 75)
    print(f"{len(hits)} symbols: {n_def} functions, {n_cls} classes")


# ── todos ────────────────────────────────────────────────────────────

TODO_RE = re.compile(r"#\s*(TODO|FIXME|HACK)\b", re.IGNORECASE)


def cmd_todos(root: Path | None = None) -> list[tuple[str, int, str]]:
    """Return (relpath, lineno, line_text) for TODO/FIXME/HACK."""
    hits: list[tuple[str, int, str]] = []
    for fp in _py_files(root):
        rel = str(fp.relative_to(BASE_DIR)).replace("\\", "/")
        try:
            lines = open(fp, encoding="utf-8", errors="ignore").readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if TODO_RE.search(line):
                hits.append((rel, i, line.rstrip()))
    return hits


def print_todos(root: Path | None = None) -> None:
    hits = cmd_todos(root)
    print(f"{'File':<45} {'Line':>5}  Comment")
    print("-" * 75)
    for rel, lineno, text in hits:
        # Show just the comment portion
        comment = text.split("#", 1)[1].strip() if "#" in text else text.strip()
        print(f"{rel:<45} {lineno:>5}  # {comment}")
    print("-" * 75)
    print(f"{len(hits)} TODO/FIXME/HACK comments found")


# ── summary ──────────────────────────────────────────────────────────

def print_summary() -> None:
    files = _py_files()
    _, total_loc = cmd_loc()
    funcs = cmd_funcs()
    todos = cmd_todos()
    n_def = sum(1 for h in funcs if h[2] == "def")
    n_cls = sum(1 for h in funcs if h[2] == "class")

    print("=" * 50)
    print("  SOVEREIGN SHARDS — CODEBASE STATISTICS")
    print("=" * 50)
    print(f"  Files:      {len(files)}")
    print(f"  Total LOC:  {total_loc}")
    print(f"  Functions:  {n_def}")
    print(f"  Classes:    {n_cls}")
    print(f"  TODOs:      {len(todos)}")
    print("=" * 50)

    print("\n— Top 10 files by LOC —")
    rows, _ = cmd_loc()
    for rel, count in rows[:10]:
        print(f"  {count:>5}  {rel}")

    if todos:
        print(f"\n— {len(todos)} TODO/FIXME/HACK comments —")
        for rel, lineno, text in todos[:10]:
            comment = text.split("#", 1)[1].strip() if "#" in text else text.strip()
            print(f"  {rel}:{lineno}  # {comment}")
        if len(todos) > 10:
            print(f"  ... and {len(todos) - 10} more")


# ── CLI ──────────────────────────────────────────────────────────────

USAGE = """Usage: python stats.py <subcommand> [path]

Subcommands:
  loc              Lines of code per module + total
  funcs [path]     List every def/class with file:line
  todos            Find TODO/FIXME/HACK comments
  summary          Combined overview
"""


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0)

    cmd = args[0].lower()
    path_arg = Path(args[1]) if len(args) > 1 else None
    if path_arg and not path_arg.is_absolute():
        path_arg = BASE_DIR / path_arg

    if cmd == "loc":
        print_loc(path_arg)
    elif cmd == "funcs":
        print_funcs(path_arg)
    elif cmd == "todos":
        print_todos(path_arg)
    elif cmd == "summary":
        print_summary()
    else:
        print(f"Unknown subcommand: {cmd}")
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()

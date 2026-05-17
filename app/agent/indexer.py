# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Project indexer: build a lightweight file tree + symbol map.

Scans the project directory and caches results to a JSON file.
Extracts function/class names from Python files via regex (no AST import needed).
USB-safe: bounded output, atomic writes.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from pathlib import Path

MAX_INDEX_FILES = 500
ALWAYS_SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv", "logs"}


def _load_gitignore(root: str) -> list[str]:
    gi = os.path.join(root, ".gitignore")
    if not os.path.isfile(gi):
        return []
    with open(gi, "r", encoding="utf-8", errors="ignore") as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


def _is_ignored(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _extract_symbols(path: str) -> list[dict[str, str]]:
    """Extract function and class names from a Python file via regex."""
    symbols = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for lineno, line in enumerate(f, 1):
                m = re.match(r"^(class|def)\s+(\w+)", line)
                if m:
                    symbols.append({
                        "type": m.group(1),
                        "name": m.group(2),
                        "line": lineno,
                    })
    except OSError:
        pass
    return symbols


def index_project(root: str) -> dict:
    """Build a project index: file tree + Python symbols.

    Returns a dict suitable for JSON serialization.
    """
    root = os.path.abspath(root)
    ignore = _load_gitignore(root) + list(ALWAYS_SKIP)
    files = []
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ALWAYS_SKIP and not _is_ignored(d, ignore)]

        for fname in sorted(filenames):
            if _is_ignored(fname, ignore):
                continue
            if count >= MAX_INDEX_FILES:
                break

            rel = os.path.relpath(os.path.join(dirpath, fname), root)
            fpath = os.path.join(dirpath, fname)
            size = 0
            try:
                size = os.path.getsize(fpath)
            except OSError:
                pass

            entry: dict = {"path": rel, "size": size}

            if fname.endswith(".py"):
                symbols = _extract_symbols(fpath)
                if symbols:
                    entry["symbols"] = symbols

            files.append(entry)
            count += 1

    return {
        "root": root,
        "file_count": len(files),
        "files": files,
    }


def save_index(root: str, output: str | None = None) -> str:
    """Build and save the project index. Returns the output path."""
    idx = index_project(root)
    if output is None:
        output = os.path.join(root, "logs", "project_index.json")
    os.makedirs(os.path.dirname(output), exist_ok=True)
    tmp = output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2, ensure_ascii=False)
    os.replace(tmp, output)
    return output


def load_index(root: str) -> dict | None:
    """Load a previously saved project index."""
    path = os.path.join(root, "logs", "project_index.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

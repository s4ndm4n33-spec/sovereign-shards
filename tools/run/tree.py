# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Recursive directory tree listing with gitignore awareness.

Usage: python tree.py [path] [--depth N]
Default depth: 4. Skips .git, __pycache__, node_modules.
"""

import fnmatch
import os
import sys


DEFAULT_DEPTH = 4
ALWAYS_SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv"}


def _load_gitignore(root: str) -> list[str]:
    gi = os.path.join(root, ".gitignore")
    if not os.path.isfile(gi):
        return []
    with open(gi, "r", encoding="utf-8", errors="ignore") as f:
        return [
            line.strip() for line in f
            if line.strip() and not line.startswith("#")
        ]


def _walk(path: str, prefix: str, depth: int, max_depth: int, ignore: list[str]) -> None:
    if depth > max_depth:
        return

    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        return

    dirs = [e for e in entries if os.path.isdir(os.path.join(path, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(path, e))]

    # Filter
    dirs = [d for d in dirs if d not in ALWAYS_SKIP and not any(
        fnmatch.fnmatch(d, p) for p in ignore
    )]
    files = [f for f in files if not any(
        fnmatch.fnmatch(f, p) for p in ignore
    )]

    all_items = dirs + files
    for i, name in enumerate(all_items):
        is_last = (i == len(all_items) - 1)
        connector = "└── " if is_last else "├── "
        full = os.path.join(path, name)

        if os.path.isdir(full):
            print(f"{prefix}{connector}{name}/")
            ext = "    " if is_last else "│   "
            _walk(full, prefix + ext, depth + 1, max_depth, ignore)
        else:
            size = os.path.getsize(full)
            if size > 1024 * 1024:
                label = f"{size / (1024*1024):.1f}MB"
            elif size > 1024:
                label = f"{size / 1024:.0f}KB"
            else:
                label = f"{size}B"
            print(f"{prefix}{connector}{name}  ({label})")


def main() -> None:
    # Force UTF-8 stdout on Windows (cp1252 can't encode box-drawing chars)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    path = "."
    max_depth = DEFAULT_DEPTH

    args = sys.argv[1:]
    if args and not args[0].startswith("--"):
        path = args.pop(0)
    if "--depth" in args:
        idx = args.index("--depth")
        if idx + 1 < len(args):
            try:
                max_depth = int(args[idx + 1])
            except ValueError:
                pass

    if not os.path.isdir(path):
        print(f"[TREE ERROR] Not a directory: {path}")
        return

    ignore = _load_gitignore(path)
    print(f"{os.path.basename(os.path.abspath(path))}/")
    _walk(path, "", 0, max_depth, ignore)


if __name__ == "__main__":
    main()

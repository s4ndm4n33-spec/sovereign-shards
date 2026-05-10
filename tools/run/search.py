"""Regex search across a directory tree. Local ripgrep alternative.

Usage: python search.py <pattern> [path] [--ext .py]
Defaults to current dir. Respects .gitignore patterns if present.
"""

import fnmatch
import os
import re
import sys

MAX_RESULTS = 200
MAX_LINE_LEN = 300


def _load_gitignore(root: str) -> list[str]:
    """Load .gitignore patterns from root."""
    gi = os.path.join(root, ".gitignore")
    if not os.path.isfile(gi):
        return []
    with open(gi, "r", encoding="utf-8", errors="ignore") as f:
        return [
            line.strip() for line in f
            if line.strip() and not line.startswith("#")
        ]


def _is_ignored(rel_path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(
            os.path.basename(rel_path), pat
        ):
            return True
    return False


def main() -> None:
    if len(sys.argv) < 2:
        print("[SEARCH ERROR] Usage: search.py <pattern> [path] [--ext .py]")
        return

    pattern = sys.argv[1]
    search_path = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "."
    ext_filter = None
    if "--ext" in sys.argv:
        idx = sys.argv.index("--ext")
        if idx + 1 < len(sys.argv):
            ext_filter = sys.argv[idx + 1]

    # ── Fault tolerance: detect reversed args ──────────────────────
    # 7B models often swap pattern and path.  If arg1 looks like a
    # file/dir that exists and arg2 does NOT exist as a path, swap.
    if (
        search_path != "."
        and os.path.exists(pattern)
        and not os.path.exists(search_path)
    ):
        pattern, search_path = search_path, pattern

    try:
        regex = re.compile(pattern)
    except re.error as exc:
        print(f"[SEARCH ERROR] Invalid regex: {exc}")
        return

    # Handle single-file search (not just directories)
    if os.path.isfile(search_path):
        hits = 0
        try:
            with open(search_path, "r", encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    if regex.search(line):
                        display = line.rstrip()
                        if len(display) > MAX_LINE_LEN:
                            display = display[:MAX_LINE_LEN] + "..."
                        print(f"{search_path}:{lineno}: {display}")
                        hits += 1
                        if hits >= MAX_RESULTS:
                            print(f"... [TRUNCATED at {MAX_RESULTS} results]")
                            return
        except (OSError, UnicodeDecodeError):
            pass
        if hits == 0:
            print(f"[SEARCH] No matches for /{pattern}/ in {search_path}")
        else:
            print(f"\n[SEARCH] {hits} match(es) found.")
        return

    ignore_patterns = _load_gitignore(search_path) + [
        ".git", "__pycache__", "*.pyc", "node_modules",
    ]

    hits = 0
    for dirpath, dirnames, filenames in os.walk(search_path):
        # Prune ignored dirs in-place
        dirnames[:] = [
            d for d in dirnames
            if not _is_ignored(d, ignore_patterns)
        ]

        for fname in filenames:
            if ext_filter and not fname.endswith(ext_filter):
                continue

            rel = os.path.relpath(os.path.join(dirpath, fname), search_path)
            if _is_ignored(rel, ignore_patterns):
                continue

            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if regex.search(line):
                            display = line.rstrip()
                            if len(display) > MAX_LINE_LEN:
                                display = display[:MAX_LINE_LEN] + "..."
                            print(f"{rel}:{lineno}: {display}")
                            hits += 1
                            if hits >= MAX_RESULTS:
                                print(f"... [TRUNCATED at {MAX_RESULTS} results]")
                                return
            except (OSError, UnicodeDecodeError):
                continue

    if hits == 0:
        print(f"[SEARCH] No matches for /{pattern}/")
    else:
        print(f"\n[SEARCH] {hits} match(es) found.")


if __name__ == "__main__":
    main()

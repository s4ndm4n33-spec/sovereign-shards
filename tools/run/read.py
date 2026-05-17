# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Read a text file with optional line limit.

Usage: python read.py <path> [max_lines]
If max_lines is given, only the first N lines are returned
with a truncation notice so the agent knows to use run_search
for specific content.
"""

import os
import sys

# Force UTF-8 output to avoid cp1252 crashes on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_MAX_LINES = 40

path = sys.argv[1] if len(sys.argv) > 1 else ""
max_lines = DEFAULT_MAX_LINES
if len(sys.argv) > 2:
    try:
        max_lines = int(sys.argv[2])
    except ValueError:
        pass

if not path:
    print("[READ ERROR] No path provided.")
elif not os.path.exists(path):
    print(f"[READ ERROR] File not found: {path}")
else:
    with open(path, encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()

    total = len(lines)
    if total <= max_lines:
        print("".join(lines), end="")
    else:
        print("".join(lines[:max_lines]), end="")
        remaining = total - max_lines
        print(f"\n[TRUNCATED — showing {max_lines}/{total} lines. "
              f"{remaining} more lines omitted. "
              f"Use run_search to find specific content.]")

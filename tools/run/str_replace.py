# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Surgical find-and-replace in a file inside the project root.

Reads JSON from stdin: {"path": "...", "old": "...", "new": "..."}
Replaces the FIRST exact occurrence of `old` with `new`.
Fails loudly if old_str is not found or appears more than once.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _path_guard import safe_path

MAX_FILE_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB FAT32 cap


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[STR_REPLACE ERROR] Invalid JSON: {exc}")
        return

    path_arg = payload.get("path", "")
    old = payload.get("old", "")
    new = payload.get("new", "")

    if not path_arg:
        print("[STR_REPLACE ERROR] Missing 'path'.")
        return
    if not old:
        print("[STR_REPLACE ERROR] Missing 'old' (the text to find).")
        return
    if old == new:
        print("[STR_REPLACE ERROR] old and new are identical — nothing to do.")
        return

    resolved = safe_path(path_arg)

    with open(resolved, "r", encoding="utf-8") as f:
        content = f.read()

    count = content.count(old)
    if count == 0:
        print(f"[STR_REPLACE ERROR] String not found in {resolved}. "
              "Verify your old_str matches exactly (whitespace matters).")
        return
    if count > 1:
        print(f"[STR_REPLACE ERROR] Found {count} occurrences in {resolved}. "
              "Narrow your old_str to match exactly one location.")
        return

    result = content.replace(old, new, 1)

    if len(result.encode("utf-8")) > MAX_FILE_BYTES:
        print("[STR_REPLACE ERROR] Result would exceed 4 GB FAT32 limit.")
        return

    tmp = str(resolved) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(result)
    os.replace(tmp, resolved)

    print(f"[STR_REPLACE OK] {resolved} — replaced 1 occurrence.")


if __name__ == "__main__":
    main()

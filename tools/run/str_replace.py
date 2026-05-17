# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Surgical find-and-replace in a file. Reads JSON from stdin.

Expected JSON: {"path": "...", "old": "...", "new": "..."}
Replaces the FIRST exact occurrence of `old` with `new`.
Fails loudly if old_str is not found or appears more than once.
"""

import json
import os
import sys

MAX_FILE_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB FAT32 cap


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[STR_REPLACE ERROR] Invalid JSON: {exc}")
        return

    path = payload.get("path", "")
    old = payload.get("old", "")
    new = payload.get("new", "")

    if not path:
        print("[STR_REPLACE ERROR] Missing 'path'.")
        return
    if not old:
        print("[STR_REPLACE ERROR] Missing 'old' (the text to find).")
        return
    if old == new:
        print("[STR_REPLACE ERROR] old and new are identical — nothing to do.")
        return

    if not os.path.isfile(path):
        print(f"[STR_REPLACE ERROR] File not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    count = content.count(old)
    if count == 0:
        print(f"[STR_REPLACE ERROR] String not found in {path}. "
              "Verify your old_str matches exactly (whitespace matters).")
        return
    if count > 1:
        print(f"[STR_REPLACE ERROR] Found {count} occurrences in {path}. "
              "Narrow your old_str to match exactly one location.")
        return

    result = content.replace(old, new, 1)

    if len(result.encode("utf-8")) > MAX_FILE_BYTES:
        print("[STR_REPLACE ERROR] Result would exceed 4 GB FAT32 limit.")
        return

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(result)
    os.replace(tmp, path)

    print(f"[STR_REPLACE OK] {path} — replaced 1 occurrence.")


if __name__ == "__main__":
    main()

# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Auto-generated tool: Fixes the editor by replacing the broken script with a working one

Built by J's tool forge.  Follows the standard tool contract:
TOOL_NAME, TOOL_DESC, and a run() function that returns a string.
"""

import os
import sys

TOOL_NAME = "run_editor_fixer"
TOOL_DESC = """Fixes the editor by replacing the broken script with a working one"""

def run(editor_path, broken_code, working_code) -> str:
    try:
        with open(editor_path, 'w') as f:
            f.write(working_code)
    except OSError as e:
        return f"[TOOL ERROR] Failed to write to {editor_path}: {e}"

    return f"Editor at {editor_path} fixed successfully"


# ── CLI entry point (tools/run convention) ───────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        print(run(*args))
    except Exception as exc:
        print(f"[TOOL ERROR] {exc}")
        sys.exit(1)

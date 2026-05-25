# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Search and replace a keyword across files in a directory inside the project root.

Built by J's tool forge.  Follows the standard tool contract:
TOOL_NAME, TOOL_DESC, and a run() function that returns a string.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _path_guard import safe_path, _ROOT

TOOL_NAME = "run_keyword_inference_replace"
TOOL_DESC = """Searches repo via keyword inference and replaces with alternative user designated keywords"""


def run(keyword, alternative_keyword, repo_path) -> str:
    # Contain repo_path to project root before touching any files
    try:
        safe_dir = safe_path(repo_path, allow_create=False)
    except SystemExit:
        return f"[TOOL ERROR] repo_path {repo_path!r} is outside the project root"

    if not safe_dir.is_dir():
        return f"[TOOL ERROR] {repo_path!r} is not a directory"

    def replace_in_file(file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if keyword not in content:
                return f"Skipped {file_path} (keyword not found)"
            updated = content.replace(keyword, alternative_keyword)
            tmp = file_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(updated)
            os.replace(tmp, file_path)
            return f"Modified {file_path}"
        except OSError as e:
            return f"[TOOL ERROR] Unable to modify {file_path}: {e}"

    try:
        results = []
        for fname in os.listdir(safe_dir):
            full = os.path.join(safe_dir, fname)
            if os.path.isfile(full):
                results.append(replace_in_file(full))
        return f"Processed {len(results)} file(s):\n" + "\n".join(results)
    except Exception as e:
        return f"[TOOL ERROR] Unexpected error: {e}"


# ── CLI entry point (tools/run convention) ───────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        print(run(*args))
    except Exception as exc:
        print(f"[TOOL ERROR] {exc}")
        sys.exit(1)

# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Auto-generated tool: Searches repo via keyword inference and replaces with alternative user designated keywords

Built by J's tool forge.  Follows the standard tool contract:
TOOL_NAME, TOOL_DESC, and a run() function that returns a string.
"""

import os
import sys

TOOL_NAME = "run_keyword_inference_replace"
TOOL_DESC = """Searches repo via keyword inference and replaces with alternative user designated keywords"""

def run(keyword, alternative_keyword, repo_path) -> str:
    def find_files(path):
        try:
            return [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        except OSError as e:
            return f"[TOOL ERROR] Unable to list files in {path}: {e}"

    def replace_in_file(file_path, keyword, alternative_keyword):
        try:
            with open(file_path, 'r+') as f:
                content = f.read()
                f.seek(0)
                f.write(content.replace(keyword, alternative_keyword))
                f.truncate()
            return f"Modified {file_path}"
        except OSError as e:
            return f"[TOOL ERROR] Unable to modify {file_path}: {e}"

    try:
        files = find_files(repo_path)
        modified_files = []
        for file in files:
            modified_files.append(replace_in_file(os.path.join(repo_path, file), keyword, alternative_keyword))
        return f"Modified files: {modified_files}"
    except Exception as e:
        return f"[TOOL ERROR] Unexpected error: {e}"


# ── CLI entry point (tools/run convention) ───────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        print(run(*args))
    except Exception as exc:
        print(f"[TOOL ERROR] {{exc}}")
        sys.exit(1)

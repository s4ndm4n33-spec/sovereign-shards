# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Sandboxed shell command execution.

Usage: echo '<command>' | python bash.py [timeout_seconds]
Default timeout: 30s. Max output: 64 KB.
"""

import subprocess
import sys

MAX_OUTPUT = 64 * 1024  # 64 KB output cap
DEFAULT_TIMEOUT = 30


def main() -> None:
    command = sys.stdin.read().strip()
    if not command:
        print("[BASH ERROR] No command provided on stdin.")
        return

    timeout = DEFAULT_TIMEOUT
    if len(sys.argv) > 1:
        try:
            timeout = int(sys.argv[1])
        except ValueError:
            pass

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",  # handle encoding issues on Windows
        )
    except subprocess.TimeoutExpired:
        print(f"[BASH ERROR] Command timed out after {timeout}s: {command[:120]}")
        return
    except Exception as exc:
        print(f"[BASH ERROR] {exc}")
        return

    output = ((result.stdout or "") + (result.stderr or "")).strip()

    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + "\n... [TRUNCATED at 64 KB]"

    if output:
        print(output)

    if result.returncode and result.returncode != 0:
        print(f"\n[EXIT {result.returncode}]")


if __name__ == "__main__":
    main()

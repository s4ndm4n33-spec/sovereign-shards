# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Run a test command and parse pass/fail results.

Usage: python test.py <command> [args...]
Example: python test.py python -m pytest tests/
Captures output, reports pass/fail summary.

Uses shell=False (via shlex.split) to prevent shell injection from
agent-controlled command arguments.
"""

import shlex
import subprocess
import sys

MAX_OUTPUT = 64 * 1024
DEFAULT_TIMEOUT = 120


def main() -> None:
    if len(sys.argv) < 2:
        print("[TEST ERROR] Usage: test.py <command> [args...]")
        print("Example: test.py python -m pytest tests/")
        return

    # Build the command list safely — no shell interpolation
    raw = " ".join(sys.argv[1:])
    try:
        cmd = shlex.split(raw)
    except ValueError as exc:
        print(f"[TEST ERROR] Cannot parse command: {exc}")
        return

    try:
        result = subprocess.run(
            cmd,
            shell=False,
            text=True,
            capture_output=True,
            timeout=DEFAULT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print(f"[TEST ERROR] Timed out after {DEFAULT_TIMEOUT}s: {raw}")
        return
    except FileNotFoundError:
        print(f"[TEST ERROR] Command not found: {cmd[0]!r}")
        return
    except Exception as exc:
        print(f"[TEST ERROR] {exc}")
        return

    output = (result.stdout or "") + (result.stderr or "")
    output = output.strip()

    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + f"\n... [TRUNCATED at {MAX_OUTPUT} bytes]"

    if output:
        print(output)

    if result.returncode == 0:
        print("\n[TEST PASSED] exit code 0")
    else:
        print(f"\n[TEST FAILED] exit code {result.returncode}")


if __name__ == "__main__":
    main()

# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Run a test command and parse pass/fail results.

Usage: python test.py <command>
Example: python test.py "python -m pytest tests/"
Captures output, reports pass/fail summary.
"""

import subprocess
import sys

MAX_OUTPUT = 64 * 1024
DEFAULT_TIMEOUT = 120


def main() -> None:
    if len(sys.argv) < 2:
        print("[TEST ERROR] Usage: test.py <command>")
        print("Example: test.py \"python -m pytest tests/\"")
        return

    command = " ".join(sys.argv[1:])

    try:
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=DEFAULT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print(f"[TEST ERROR] Timed out after {DEFAULT_TIMEOUT}s: {command}")
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

# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Sandboxed shell command execution.

Usage: echo '<command>' | python bash.py [timeout_seconds]
Default timeout: 30s. Max output: 64 KB.
"""

import re
import subprocess
import sys

MAX_OUTPUT = 64 * 1024  # 64 KB output cap
DEFAULT_TIMEOUT = 30

# Commands that must never execute regardless of exec permission level.
# These patterns block the most dangerous shell primitives: destructive deletes,
# remote code execution via pipe, package installation, and reverse shells.
_BLOCKED_PATTERNS = [
    r"\brm\s+-[rRfF]*[fF][rRfF]*\b",        # rm -rf / rm -fr variants
    r"\brm\s+--force\b",
    r"\brmdir\s+/[sS]\b",                    # rmdir /s (Windows recursive)
    r"\bdel\s+/[sqSQ]\b",                    # del /s /q
    r"\bformat\s+[a-zA-Z]:\b",              # format C:
    r"\bcurl\b[^|]*\|\s*(ba)?sh\b",         # curl ... | bash
    r"\bwget\b[^|]*\|\s*(ba)?sh\b",         # wget ... | bash
    r"\bpip\s+install\b",                    # package installation
    r"\bapt(?:-get)?\s+install\b",
    r"\byum\s+install\b",
    r"\bchmod\s+[0-7]*7[0-7]*\b",           # world-writable/executable
    r"\bchown\s+.*\broo[tT]\b",             # chown to root
    r"\b(nc|ncat|netcat)\b.*-[eE]\b",       # reverse shell via netcat
    r"\bpowershell\b.*-[Ee]nc(?:odedCommand)?\b",  # encoded PS payloads
    r"\b(?:bash|sh|cmd)\s+-[cC]\s+['\"]",  # inline shell execution
    r">\s*/etc/(?:passwd|shadow|hosts)",    # overwrite critical system files
    r">\s*[A-Za-z]:\\[Ww]indows\\",        # overwrite Windows system files
    r"\bdd\b.*\bof=/dev/[sh]d",            # disk wipe via dd
    r"\bmkfs\b",                            # filesystem format
    r":\(\)\s*\{.*:\|:&\s*\}",             # fork bomb
]


def _is_blocked(command: str) -> bool:
    return any(re.search(p, command, re.IGNORECASE | re.DOTALL) for p in _BLOCKED_PATTERNS)


def main() -> None:
    command = sys.stdin.read().strip()
    if not command:
        print("[BASH ERROR] No command provided on stdin.")
        return

    if _is_blocked(command):
        print(f"[BASH BLOCKED] Command matches denylist and was not executed: {command[:120]}")
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
            shell=True,  # nosec B602 — intentional: bash.py is J's shell executor; denylist above gates dangerous commands
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

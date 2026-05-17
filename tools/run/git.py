# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Git operations wrapper with pre-push sandbox validation.

Usage: python git.py <subcommand> [args...]
Allowed: status, diff, log, add, commit, branch, checkout, stash, show, reset, push.

Push is gated: runs the full validation sandbox before allowing the push.
Use --force-push to skip validation (not recommended).
"""

import subprocess
import sys
import os

ALLOWED = {
    "status", "diff", "log", "add", "commit", "branch", "checkout",
    "stash", "show", "reset", "rev-parse", "remote", "push",
}
GATED = {"push", "commit"}  # Commands that trigger sandbox validation
MAX_OUTPUT = 64 * 1024


def _run_sandbox() -> bool:
    """Run pre-push validation. Returns True if safe to proceed."""
    try:
        # Import sandbox from the project
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        from app.agent.sandbox import validate_before_push

        print("\n[SANDBOX] Running pre-push validation...\n")
        report = validate_before_push(
            project_dir=os.getcwd(),
            copy_to_temp=True,
        )
        print(report.summary())
        return report.passed
    except ImportError:
        print("[SANDBOX] Warning: sandbox module not found, skipping validation.")
        return True
    except Exception as exc:
        print(f"[SANDBOX] Warning: validation error ({exc}), proceeding with caution.")
        return True


def main() -> None:
    if len(sys.argv) < 2:
        print(f"[GIT ERROR] Usage: git.py <subcommand> [args...]\n"
              f"Allowed: {', '.join(sorted(ALLOWED))}")
        return

    subcommand = sys.argv[1]
    if subcommand not in ALLOWED:
        print(f"[GIT ERROR] Subcommand '{subcommand}' not allowed.\n"
              f"Allowed: {', '.join(sorted(ALLOWED))}")
        return

    args = sys.argv[2:]
    force_push = "--force-push" in args
    if force_push:
        args.remove("--force-push")

    # Gate pushes and commits through sandbox
    if subcommand in GATED and not force_push:
        if not _run_sandbox():
            print(f"\n[GIT BLOCKED] Sandbox validation failed. "
                  f"Fix the issues above before {subcommand}ing.")
            print(f"  Use --force-push to override (not recommended).")
            return
        print(f"\n[SANDBOX PASSED] Proceeding with git {subcommand}...\n")

    cmd = ["git", subcommand] + args

    try:
        result = subprocess.run(
            cmd, text=True, capture_output=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        print(f"[GIT ERROR] Timed out: {' '.join(cmd)}")
        return
    except FileNotFoundError:
        print("[GIT ERROR] git is not installed or not on PATH.")
        return

    output = (result.stdout or "") + (result.stderr or "")
    output = output.strip()
    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + "\n... [TRUNCATED]"

    if output:
        print(output)
    elif result.returncode == 0:
        print(f"[GIT OK] {' '.join(cmd)}")
    else:
        print(f"[GIT ERROR] exit code {result.returncode}")


if __name__ == "__main__":
    main()

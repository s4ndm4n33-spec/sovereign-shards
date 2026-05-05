"""Sandboxed shell command execution with streaming output.

Usage: echo '<command>' | python bash.py [timeout_seconds]
Default timeout: 30s. Max output: 64 KB.

Output streams line-by-line in real time so the operator sees
progress during long builds, installs, and test runs.
"""

import subprocess
import sys
import threading

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

    # Stream output in real time
    captured: list[str] = []
    total_bytes = 0
    truncated = False

    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        print(f"[BASH ERROR] {exc}")
        return

    def _drain() -> None:
        nonlocal total_bytes, truncated
        try:
            for line in iter(proc.stdout.readline, ""):
                if truncated:
                    break
                total_bytes += len(line)
                if total_bytes > MAX_OUTPUT:
                    truncated = True
                    captured.append(f"\n... [TRUNCATED at {MAX_OUTPUT} bytes]")
                    break
                captured.append(line)
                sys.stdout.write(f"  │ {line}")
                sys.stdout.flush()
        except (ValueError, OSError):
            pass
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass

    drain_thread = threading.Thread(target=_drain, daemon=True)
    drain_thread.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        timed_out = True

    drain_thread.join(timeout=5)

    if timed_out:
        print(f"\n[BASH ERROR] Command timed out after {timeout}s: {command[:120]}")

    if proc.returncode and proc.returncode != 0 and not timed_out:
        print(f"\n[EXIT {proc.returncode}]")


if __name__ == "__main__":
    main()

# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Streaming tool output — real-time stdout/stderr during long operations.

Instead of waiting for a subprocess to finish, this module streams
output line-by-line so the operator sees progress immediately.

USB-safe: bounded buffer, configurable timeout, no external deps.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

MAX_OUTPUT = 64 * 1024  # 64 KB capture cap
DEFAULT_TIMEOUT = 60


@dataclass
class StreamResult:
    """Captured output from a streaming subprocess."""
    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    timed_out: bool = False
    truncated: bool = False

    @property
    def output(self) -> str:
        """Combined output for tool result injection."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[STDERR]\n{self.stderr}")
        if self.timed_out:
            parts.append(f"[TIMED OUT after {DEFAULT_TIMEOUT}s]")
        if self.truncated:
            parts.append(f"[TRUNCATED at {MAX_OUTPUT} bytes]")
        return "\n".join(parts)


def stream_subprocess(
    command: str | list[str],
    *,
    shell: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
    cwd: str | None = None,
    max_output: int = MAX_OUTPUT,
    prefix: str = "  │ ",
    quiet: bool = False,
) -> StreamResult:
    """Run a subprocess with real-time line-by-line output streaming.

    Args:
        command: Shell command string or arg list.
        shell: Use shell mode (default True for bash-style commands).
        timeout: Max seconds before killing the process.
        cwd: Working directory.
        max_output: Max bytes to capture (prevents memory bloat on USB).
        prefix: Line prefix for streamed output (visual indent).
        quiet: If True, capture but don't print to terminal.

    Returns:
        StreamResult with captured output and metadata.
    """
    result = StreamResult()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    total_bytes = 0
    truncated = False

    try:
        proc = subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            bufsize=1,  # Line-buffered
        )
    except Exception as exc:
        result.stderr = f"[STREAM ERROR] Failed to start: {exc}"
        return result

    def _drain(pipe, sink: list[str], label: str) -> None:
        """Read lines from a pipe, print them live, append to sink."""
        nonlocal total_bytes, truncated
        try:
            for line in iter(pipe.readline, ""):
                if truncated:
                    break
                total_bytes += len(line)
                if total_bytes > max_output:
                    truncated = True
                    break
                sink.append(line)
                if not quiet:
                    # Print with prefix, strip trailing newline to avoid double-spacing
                    sys.stdout.write(f"{prefix}{line}")
                    sys.stdout.flush()
        except (ValueError, OSError):
            pass  # Pipe closed
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    # Drain stdout and stderr in parallel threads
    t_out = threading.Thread(target=_drain, args=(proc.stdout, stdout_lines, "stdout"), daemon=True)
    t_err = threading.Thread(target=_drain, args=(proc.stderr, stderr_lines, "stderr"), daemon=True)
    t_out.start()
    t_err.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        result.timed_out = True

    # Wait for drain threads to finish (they'll EOF after proc dies)
    t_out.join(timeout=5)
    t_err.join(timeout=5)

    result.stdout = "".join(stdout_lines)
    result.stderr = "".join(stderr_lines)
    result.returncode = proc.returncode or -1
    result.truncated = truncated

    return result


def stream_python(
    code: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    cwd: str | None = None,
    quiet: bool = False,
) -> StreamResult:
    """Run a Python code snippet with streaming output.

    This is the streaming equivalent of exec.py — runs the code in a
    subprocess so output appears line-by-line.
    """
    return stream_subprocess(
        [sys.executable, "-c", code],
        shell=False,
        timeout=timeout,
        cwd=cwd,
        quiet=quiet,
        prefix="  │ ",
    )

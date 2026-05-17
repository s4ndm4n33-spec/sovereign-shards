# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Helpers for running a local llama.cpp server from the shard itself.

Supports Vulkan GPU offload, CPU-only fallback, and memory-conscious defaults.

Build-safe: only passes flags that are universally supported across llama.cpp
versions.  Optional / newer flags (--reasoning-*, --device) are gated behind
non-default config values so older binaries still boot cleanly.
"""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen

from app.client import RuntimeConfig


BASE_DIR = Path(__file__).resolve().parent.parent
SERVER_LOG_DIR = BASE_DIR / "logs" / "server"
SERVER_LOG_DIR.mkdir(parents=True, exist_ok=True)


class LocalLlamaServer:
    """Launch and manage a shard-local llama.cpp server when needed."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.process: subprocess.Popen | None = None
        self.log_handle = None
        self.started_by_us = False
        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        self.log_path = SERVER_LOG_DIR / f"{timestamp}.log"

    def _is_ready(self) -> bool:
        """Return True when the local server answers HTTP requests."""
        try:
            request = Request(f"{self.config.base_url}/v1/models", method="GET")
            with urlopen(request, timeout=3):
                return True
        except Exception:
            return False

    def _build_command(self) -> list[str]:
        """Build the llama-server command line with hardware-aware flags.

        Only includes universally supported flags by default.  Newer flags
        (--reasoning-budget, --reasoning-format, --device) are only added
        when the user explicitly sets non-default values, keeping the
        command compatible with older llama.cpp builds.
        """
        cfg = self.config

        # ── Core flags (supported by every llama.cpp server build) ────
        command = [
            str(cfg.server_binary),
            "--model", str(cfg.model_path),
            "--host", cfg.host,
            "--port", str(cfg.port),
            "--ctx-size", str(cfg.num_ctx),
            "--threads", str(cfg.num_thread),
            "--batch-size", str(cfg.batch_size),
            "--temp", str(cfg.temperature),
            "--top-p", str(cfg.top_p),
            "--top-k", str(cfg.top_k),
            "--min-p", str(cfg.min_p),
            "--alias", cfg.model,
            "--jinja",
            "--chat-template-file", str(cfg.chat_template_file),
            "--n-predict", str(cfg.num_predict),
            "--no-warmup",
            "--no-webui",
        ]

        # ── Reasoning flags (newer builds only) ──────────────────────
        # Only include when explicitly configured.  Default (budget=0,
        # format=none) means "no reasoning" → skip the flags entirely
        # so older binaries don't choke on them.
        if cfg.reasoning_budget > 0:
            command.extend(["--reasoning-budget", str(cfg.reasoning_budget)])
        if cfg.reasoning_format and cfg.reasoning_format != "none":
            command.extend(["--reasoning-format", cfg.reasoning_format])

        # ── GPU / Device offload ──────────────────────────────────────
        # gpu_device: "auto" = let llama.cpp detect (Vulkan, CUDA, Metal)
        #             "vulkan" = force Vulkan
        #             "cuda"   = force CUDA
        #             "none"   = CPU only, no GPU
        device = cfg.gpu_device

        if device == "none":
            # Force CPU-only — always pass explicit zero to override defaults
            command.extend(["--gpu-layers", "0"])
        else:
            if device != "auto":
                # Force a specific backend (vulkan, cuda, etc.)
                command.extend(["--device", device])
            if cfg.gpu_layers > 0:
                command.extend(["--gpu-layers", str(cfg.gpu_layers)])

        return command

    def ensure_started(self) -> None:
        """Start the shard-local server if this backend needs one."""
        if self.config.backend != "llama_cpp":
            return

        if self._is_ready():
            return

        if not self.config.server_binary.exists():
            raise RuntimeError(f"Missing server binary: {self.config.server_binary}")
        if not self.config.model_path.exists():
            raise RuntimeError(f"Missing model file: {self.config.model_path}")

        command = self._build_command()

        env = os.environ.copy()
        env["PATH"] = f"{self.config.server_binary.parent}{os.pathsep}{env.get('PATH', '')}"
        if not self.config.chat_template_kwargs:
            env.pop("LLAMA_CHAT_TEMPLATE_KWARGS", None)

        self.log_handle = self.log_path.open("w", encoding="utf-8")

        # Log the exact command for debugging
        self.log_handle.write(f"CMD: {' '.join(command)}\n\n")
        self.log_handle.flush()

        self.process = subprocess.Popen(
            command,
            cwd=self.config.server_binary.parent,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            env=env,
        )
        self.started_by_us = True

        deadline = time.time() + self.config.startup_timeout
        while time.time() < deadline:
            if self._is_ready():
                return
            if self.process.poll() is not None:
                tail = self.log_path.read_text(encoding="utf-8", errors="ignore")
                raise RuntimeError(
                    "Local llama server exited during startup.\n"
                    f"Log: {self.log_path}\n{tail[-2000:]}"
                )
            time.sleep(1)

        raise RuntimeError(
            "Timed out waiting for the local llama server to start.\n"
            f"Log: {self.log_path}"
        )

    def stop(self) -> None:
        """Stop the server only if this process launched it."""
        if not self.started_by_us or self.process is None:
            return

        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self.log_handle is not None:
            self.log_handle.close()

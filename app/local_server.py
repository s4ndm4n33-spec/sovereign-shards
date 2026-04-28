"""Helpers for running a local llama.cpp server from the shard itself."""

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

        command = [
            str(self.config.server_binary),
            "--model",
            str(self.config.model_path),
            "--device",
            "none",
            "--host",
            self.config.host,
            "--port",
            str(self.config.port),
            "--ctx-size",
            str(self.config.num_ctx),
            "--threads",
            str(self.config.num_thread),
            "--temp",
            str(self.config.temperature),
            "--top-p",
            str(self.config.top_p),
            "--top-k",
            str(self.config.top_k),
            "--min-p",
            str(self.config.min_p),
            "--alias",
            self.config.model,
            "--jinja",
            "--chat-template-file",
            str(self.config.chat_template_file),
            "--reasoning-budget",
            str(self.config.reasoning_budget),
            "--reasoning-format",
            self.config.reasoning_format,
            "--n-predict",
            str(self.config.num_predict),
            "--no-warmup",
            "--no-webui",
        ]
        if self.config.chat_template_kwargs:
            command.extend(
                [
                    "--chat-template-kwargs",
                    self.config.chat_template_kwargs,
                ]
            )

        env = os.environ.copy()
        env["PATH"] = f"{self.config.server_binary.parent};{env.get('PATH', '')}"
        if not self.config.chat_template_kwargs:
            env.pop("LLAMA_CHAT_TEMPLATE_KWARGS", None)
        self.log_handle = self.log_path.open("w", encoding="utf-8")
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

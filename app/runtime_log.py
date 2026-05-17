# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Structured runtime logging with simple rotation for USB-safe operation."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_LOG_DIR = BASE_DIR / "logs" / "runtime"
RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 512 * 1024
MAX_FILES = 5


class RuntimeJsonLogger:
    """Append JSONL events to a rotated runtime log file."""

    def __init__(self, session_id: str) -> None:
        self.path = RUNTIME_LOG_DIR / f"{session_id}.jsonl"

    def event(self, name: str, **fields: object) -> None:
        """Write one structured event row and rotate if needed."""
        self._rotate_if_needed()
        payload = {
            "timestamp": datetime.now().astimezone().isoformat(),
            "event": name,
            **fields,
        }
        line = json.dumps(payload, ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    def _rotate_if_needed(self) -> None:
        if self.path.exists() and self.path.stat().st_size < MAX_BYTES:
            return

        if self.path.exists():
            for index in range(MAX_FILES - 1, 0, -1):
                old = self.path.with_suffix(f".jsonl.{index}")
                new = self.path.with_suffix(f".jsonl.{index + 1}")
                if old.exists():
                    if index + 1 > MAX_FILES:
                        old.unlink(missing_ok=True)
                    else:
                        old.replace(new)
            self.path.replace(self.path.with_suffix(".jsonl.1"))

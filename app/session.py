# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Timestamped session logging helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = BASE_DIR / "logs" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SessionLogger:
    """Persist session metadata and transcript with timestamps."""

    model: str
    started_at: datetime = field(default_factory=lambda: datetime.now().astimezone())

    def __post_init__(self) -> None:
        self.session_id = self.started_at.strftime("%Y%m%d-%H%M%S")
        self.transcript_path = SESSIONS_DIR / f"{self.session_id}.md"
        self.metadata_path = SESSIONS_DIR / f"{self.session_id}.json"
        self._write_metadata()
        self.transcript_path.write_text(
            f"# Sovereign Shard Session\n\nstarted_at: {self.started_at.isoformat()}\n"
            f"model: {self.model}\n\n",
            encoding="utf-8",
        )

    def _write_metadata(self) -> None:
        self.metadata_path.write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "started_at": self.started_at.isoformat(),
                    "model": self.model,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def append(self, role: str, content: str) -> None:
        """Append a timestamped transcript block."""
        timestamp = datetime.now().astimezone().isoformat()
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {role.upper()}\n{content}\n\n")

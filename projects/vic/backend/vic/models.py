"""Canonical conversation model for V.I.C.

All provider parsers normalize into this shape so downstream stages
(clustering, extraction, reporting) are backend-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Provider = Literal["gemini", "chatgpt", "claude", "unknown"]


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system" | "model"
    content: str
    timestamp: datetime | None = None


@dataclass
class Conversation:
    provider: str
    source_file: str
    raw_id: str
    title: str
    messages: list[Message] = field(default_factory=list)
    created: datetime | None = None
    updated: datetime | None = None

    def full_text(self) -> str:
        parts: list[str] = []
        for m in self.messages:
            tag = m.role or "msg"
            parts.append(f"{tag}: {m.content}")
        return "\n".join(parts)

    def date_iso(self) -> str:
        d = self.created or self.updated
        return d.strftime("%Y-%m-%d") if d else "unknown"

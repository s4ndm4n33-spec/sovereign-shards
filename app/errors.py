# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Runtime error taxonomy for deterministic failure handling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShardRuntimeError(RuntimeError):
    """Base typed runtime error with an explicit error code."""

    code: str
    message: str
    detail: str = ""

    def __str__(self) -> str:
        suffix = f" | detail={self.detail}" if self.detail else ""
        return f"[{self.code}] {self.message}{suffix}"


class StartupError(ShardRuntimeError):
    """Raised for startup and dependency failures."""


class TransportError(ShardRuntimeError):
    """Raised for backend transport and streaming failures."""


class ConfigurationError(ShardRuntimeError):
    """Raised for invalid or missing runtime configuration."""

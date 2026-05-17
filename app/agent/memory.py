# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Cross-session memory: persist learnings and preferences.

Stores key-value facts in a simple JSON file.
USB-safe: atomic writes, bounded size (64KB cap).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEMORY_PATH = BASE_DIR / "logs" / "memory.json"
MAX_MEMORY_BYTES = 64 * 1024  # 64 KB


def _load() -> dict[str, str]:
    if not MEMORY_PATH.exists():
        return {}
    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, str]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    if len(payload.encode("utf-8")) > MAX_MEMORY_BYTES:
        # Prune oldest entries until it fits
        while len(payload.encode("utf-8")) > MAX_MEMORY_BYTES and data:
            oldest_key = next(iter(data))
            del data[oldest_key]
            payload = json.dumps(data, indent=2, ensure_ascii=False)

    tmp = str(MEMORY_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp, str(MEMORY_PATH))


def remember(key: str, value: str) -> None:
    """Store a fact."""
    data = _load()
    data[key] = value
    _save(data)


def recall(key: str) -> str | None:
    """Retrieve a fact."""
    return _load().get(key)


def recall_all() -> dict[str, str]:
    """Return all stored facts."""
    return _load()


def forget(key: str) -> bool:
    """Remove a fact. Returns True if it existed."""
    data = _load()
    if key in data:
        del data[key]
        _save(data)
        return True
    return False

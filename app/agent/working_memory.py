"""Tier 2: Working Memory — rolling structured summaries.

Append-only JSONL log of step/turn summaries.
USB-safe: atomic writes, size-bounded.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = BASE_DIR / "memory"
WM_PATH = MEMORY_DIR / "working_memory.jsonl"
MAX_WM_BYTES = 32 * 1024  # 32 KB — reflection trigger threshold


def _ensure_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def append(step: str, result: str, issue: str | None = None,
           decision: str | None = None) -> None:
    """Append a structured summary entry."""
    _ensure_dir()
    entry: dict = {"ts": time.time(), "step": step, "result": result}
    if issue:
        entry["issue"] = issue
    if decision:
        entry["decision"] = decision
    with open(WM_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_recent(n: int = 10) -> list[dict]:
    """Read last N entries."""
    return read_all()[-n:]


def read_all() -> list[dict]:
    """Read all entries."""
    if not WM_PATH.exists():
        return []
    entries: list[dict] = []
    try:
        with open(WM_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return entries


def size_bytes() -> int:
    """Current file size in bytes."""
    try:
        return os.path.getsize(WM_PATH) if WM_PATH.exists() else 0
    except OSError:
        return 0


def needs_reflection() -> bool:
    """True when working memory exceeds the weight threshold."""
    return size_bytes() > MAX_WM_BYTES


def replace_entries(entries: list[dict]) -> None:
    """Atomic replace of all entries (used after reflection)."""
    _ensure_dir()
    tmp = str(WM_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    os.replace(tmp, str(WM_PATH))


def format_for_context(entries: list[dict]) -> str:
    """Format entries as compact text for injection into active context."""
    if not entries:
        return ""
    lines = ["[WORKING MEMORY — recent steps]"]
    for e in entries:
        parts = [f"• {e.get('step', '?')}: {e.get('result', '?')}"]
        if e.get("issue"):
            parts.append(f"  ⚠ {e['issue']}")
        if e.get("decision"):
            parts.append(f"  → {e['decision']}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


def compress_turn(user_msg: str, assistant_reply: str) -> dict:
    """Heuristic compression of a turn into a working memory entry.

    No LLM call — pure text extraction.  Fast and free.
    """
    step = user_msg[:150].replace("\n", " ").strip()
    result = assistant_reply[:200].replace("\n", " ").strip()

    issue = None
    for marker in ("ERROR", "FAILED", "error:", "exception", "Traceback"):
        if marker.lower() in assistant_reply.lower():
            for line in assistant_reply.split("\n"):
                if marker.lower() in line.lower():
                    issue = line.strip()[:150]
                    break
            break

    decision = None
    for marker in ("chose", "decided", "using", "switching to", "will use", "selected"):
        if marker in assistant_reply.lower():
            for line in assistant_reply.split("\n"):
                if marker in line.lower():
                    decision = line.strip()[:150]
                    break
            break

    return {"step": step, "result": result, "issue": issue, "decision": decision}

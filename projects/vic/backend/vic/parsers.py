"""Conversation parsers for each supported provider.

Each parser yields :class:`Conversation` objects. Parsers tolerate
missing fields, malformed JSON, and large archives — they never raise
on a single broken file, logging the skip instead.
"""

from __future__ import annotations

import json
import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import Conversation, Message

log = logging.getLogger("vic.parsers")

_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value) / 1000.0 if value > 1e12 else float(value))
        except (OSError, ValueError, OverflowError, ArithmeticError):
            return None
    if isinstance(value, str):
        v = value.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(v[: len(v.rstrip("Z"))] + ("Z" if v.endswith("Z") else ""), fmt) if fmt.endswith("Z") else datetime.strptime(v, fmt)
            except ValueError:
                continue
        # Python's fromisoformat handles most ISO strings from 3.11+
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


def _coerce_text(value) -> str:
    """Coerce a ChatGPT/Claude content field (string or list-of-parts) into text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    parts: list[str] = []
    if isinstance(value, list):
        for piece in value:
            if isinstance(piece, str):
                parts.append(piece)
            elif isinstance(piece, dict):
                t = piece.get("text") or piece.get("content") or piece.get("value")
                if isinstance(t, str):
                    parts.append(t)
                elif isinstance(t, list):
                    parts.append(_coerce_text(t))
    return "\n".join(p for p in parts if p).strip()


# ---------------------------------------------------------------------------
# ChatGPT (conversations.json)
# ---------------------------------------------------------------------------

def parse_chatgpt_json(data, source_file: str) -> Iterator[Conversation]:
    if isinstance(data, dict):  # single conversation wrapped
        data = [data]
    if not isinstance(data, list):
        return
    for entry in data:
        try:
            cid = str(entry.get("id") or entry.get("conversation_id") or "")
            title = entry.get("title") or "(untitled)"
            create_dt = _parse_dt(entry.get("create_time"))
            update_dt = _parse_dt(entry.get("update_time"))
            msgs: list[Message] = []
            mapping = entry.get("mapping") or {}
            # Build nodes; take only visible branches (root -> ... -> current)
            nodes = {}
            for node_id, node in mapping.items():
                if not isinstance(node, dict):
                    continue
                nodes[node_id] = node
            # Walk children in order; ChatGPT stores parent links.
            ordered: list[Message] = []
            seen = set()
            # Find root(s) = nodes with no parent pointer in mapping
            roots = [nid for nid, n in nodes.items() if not n.get("parent")]
            stack = list(roots)
            while stack:
                nid = stack.pop(0)
                if nid in seen:
                    continue
                seen.add(nid)
                node = nodes.get(nid) or {}
                m = node.get("message")
                if isinstance(m, dict):
                    role = m.get("author", {}).get("role") or "unknown"
                    if role == "tool":
                        role = "assistant"
                    content = _coerce_text(m.get("content") and m.get("content").get("parts"))
                    if not content:
                        content = _coerce_text(m.get("content"))
                    ts = _parse_dt(m.get("create_time"))
                    if content:
                        ordered.append(Message(role=role, content=content, timestamp=ts))
                # push children in order
                children = node.get("children") or []
                stack[:0] = list(children)
            if not ordered:
                # Fallback: linear scan of mapping values
                for nid, node in nodes.items():
                    m = node.get("message")
                    if isinstance(m, dict):
                        role = m.get("author", {}).get("role") or "unknown"
                        content = _coerce_text(m.get("content") and m.get("content").get("parts"))
                        if content:
                            ordered.append(Message(role=role, content=content, timestamp=_parse_dt(m.get("create_time"))))
            conv = Conversation(
                provider="chatgpt",
                source_file=source_file,
                raw_id=cid,
                title=title,
                messages=ordered,
                created=create_dt,
                updated=update_dt,
            )
            yield conv
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping ChatGPT entry %s: %s", entry.get("id"), exc)


def parse_chatgpt_file(path: Path) -> Iterator[Conversation]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed parsing %s: %s", path, exc)
        return
    yield from parse_chatgpt_json(data, str(path))


# ---------------------------------------------------------------------------
# Claude (multiple JSON files; each may be a single conv or list)
# ---------------------------------------------------------------------------

_CLAUDE_FIELD_TITLE = ("title", "name", "summary")
_CLAUDE_FIELD_ID = ("id", "uuid", "conversation_id", "session_id")


def parse_claude_file(path: Path) -> Iterator[Conversation]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed parsing Claude file %s: %s", path, exc)
        return
    if isinstance(data, dict):
        yield from _parse_one_claude(data, str(path))
    elif isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                yield from _parse_one_claude(entry, str(path))


def _parse_one_claude(entry: dict, source: str) -> Iterator[Conversation]:
    try:
        cid = ""
        for k in _CLAUDE_FIELD_ID:
            if entry.get(k):
                cid = str(entry.get(k))
                break
        title = ""
        for k in _CLAUDE_FIELD_TITLE:
            v = entry.get(k)
            if isinstance(v, str) and v:
                title = v
                break
        if not title:
            title = "(untitled)"
        create_dt = _parse_dt(entry.get("created_at") or entry.get("createdAt") or entry.get("start"))
        update_dt = _parse_dt(entry.get("updated_at") or entry.get("updatedAt") or entry.get("end"))
        msgs: list[Message] = []

        # Claude exports vary wildly. Try common shapes.
        chat_messages = (
            entry.get("chat_messages")
            or entry.get("messages")
            or entry.get("message")
            or entry.get("turns")
            or []
        )
        if isinstance(chat_messages, dict):
            chat_messages = [chat_messages]
        if isinstance(chat_messages, list):
            for m in chat_messages:
                if not isinstance(m, dict):
                    continue
                role = m.get("sender") or m.get("role") or m.get("author") or "user"
                if isinstance(role, dict):
                    role = role.get("role") or "user"
                role = str(role)
                if role.lower() == "human":
                    role = "user"
                content = _coerce_text(m.get("text") or m.get("content") or m.get("message"))
                if not content:
                    # Sometimes content is a list of blocks
                    blocks = m.get("content") or []
                    if isinstance(blocks, list):
                        content = _coerce_text(blocks)
                ts = _parse_dt(m.get("created_at") or m.get("createdAt") or m.get("timestamp"))
                if content:
                    msgs.append(Message(role=role, content=content, timestamp=ts))

        # Fallback: top-level text fields
        if not msgs:
            prompt = entry.get("prompt") or entry.get("input") or ""
            resp = entry.get("response") or entry.get("output") or ""
            if prompt:
                msgs.append(Message(role="user", content=str(prompt), timestamp=create_dt))
            if resp:
                msgs.append(Message(role="assistant", content=str(resp), timestamp=update_dt))

        yield Conversation(
            provider="claude",
            source_file=source,
            raw_id=cid,
            title=title,
            messages=msgs,
            created=create_dt,
            updated=update_dt,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Skipping Claude entry in %s: %s", source, exc)


# ---------------------------------------------------------------------------
# Gemini (Google Takeout "Gemini" My Activity JSON)
# ---------------------------------------------------------------------------

_GEMINI_TEXT_KEYS = ("text", "title", "value", "query", "prompt", "subtitle")
_GEMINI_TIME_KEYS = ("time", "timestamp", "date")


def parse_gemini_file(path: Path | str | dict | list) -> Iterator[Conversation]:
    """Parse a Gemini My Activity / Takeout JSON file or in-memory data.

    Accepts a filesystem path or a pre-parsed dict/list (used when reading
    ZIP members in memory). Gemini's Takeout splits exchanges across one
    or many JSON entries; each entry is normalized into a one-turn
    Conversation and downstream clustering merges adjacent ones into sessions.
    """
    data: object
    source = ""
    if isinstance(path, (dict, list)):
        data = path
        source = "<in-memory>"
    else:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed parsing Gemini file %s: %s", path, exc)
            return
    entries = data
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            entries = data["items"]
        elif isinstance(data.get("events"), list):
            entries = data["events"]
        else:
            entries = [data]
    if not isinstance(entries, list):
        return
    grouped: list[Conversation] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            text = ""
            for k in _GEMINI_TEXT_KEYS:
                v = entry.get(k)
                if isinstance(v, str) and v:
                    text = v
                    break
                if isinstance(v, list):
                    text = _coerce_text(v)
                    if text:
                        break
            if not text and entry.get("header") and isinstance(entry["header"], dict):
                text = entry["header"].get("title") or entry["header"].get("name") or ""
            # subtitle is common in Gemini My Activity ("Searched X")
            subtitle = entry.get("subtitles")
            if isinstance(subtitle, list) and not text:
                text = _coerce_text(subtitle)
            if not text:
                continue
            text = str(text).strip()
            ts = None
            for k in _GEMINI_TIME_KEYS:
                v = entry.get(k)
                if v:
                    ts = _parse_dt(v)
                    if ts:
                        break
            title = text[:120] + ("…" if len(text) > 120 else "")
            msgs = [Message(role="user", content=text, timestamp=ts)]
            conv = Conversation(
                provider="gemini",
                source_file=source,
                raw_id=str(entry.get("id") or entry.get("time") or ts or ""),
                title=title,
                messages=msgs,
                created=ts,
                updated=ts,
            )
            grouped.append(conv)
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping Gemini entry %s: %s", entry.get("id"), exc)
    yield from _coalesce_gemini(grouped)


def _coalesce_gemini(items: list[Conversation], gap_minutes: int = 30) -> Iterator[Conversation]:
    """Merge consecutive Gemini entries within `gap_minutes` into one Conversation.

    Gemini's My Activity exports each turn as a row. Treating each as its
    own session destroys chronological context, so we coalesce adjacent
    entries that share a timestamp window.
    """
    items = [c for c in items if c.created is not None or c.messages]
    items.sort(key=lambda c: c.created or datetime.min)
    if not items:
        return
    current = items[0]
    current_buffer = list(current.messages)
    last_ts = current.created
    current_title = current.title
    for nxt in items[1:]:
        ts = nxt.created
        merge = (
            last_ts is not None
            and ts is not None
            and abs((ts - last_ts).total_seconds()) <= gap_minutes * 60
        )
        if merge and ts is not None:
            current_buffer.extend(nxt.messages)
            current_buffer.append(
                Message(role="assistant", content="(Gemini response recorded as separate activity entry)", timestamp=ts)
            )
            last_ts = ts
            continue
        # Flush
        current.messages = current_buffer
        current.title = current_title or current.title
        yield current
        current = nxt
        current_buffer = list(nxt.messages)
        last_ts = nxt.created
        current_title = nxt.title
    current.messages = current_buffer
    yield current


# ---------------------------------------------------------------------------
# ZIP extraction + dispatcher
# ---------------------------------------------------------------------------

def extract_conversations_from_zip(zip_path: Path) -> Iterator[Conversation]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        lower_joined = " ".join(n.lower() for n in names)
        # ChatGPT
        if "conversations.json" in {n.lower() for n in names} or any(n.endswith("conversations.json") for n in names):
            for n in names:
                if n.lower().endswith("conversations.json"):
                    try:
                        raw = zf.read(n)
                        data = json.loads(raw)
                        yield from parse_chatgpt_json(data, n)
                    except (json.JSONDecodeError, KeyError, zipfile.BadZipFile, OSError) as exc:
                        log.warning("Failed reading %s from %s: %s", n, zip_path, exc)
            return
        # Gemini Takeout: walk JSON files under Gemini/My Activity
        for n in names:
            ln = n.lower()
            if "gemini" in ln and ln.endswith(".json"):
                try:
                    raw = zf.read(n)
                    data = json.loads(raw)
                    # Gemini My Activity is often one big file with many entries
                    yield from parse_gemini_file(data)
                except (json.JSONDecodeError, KeyError, zipfile.BadZipFile, OSError) as exc:
                    log.warning("Failed reading Gemini member %s: %s", n, exc)


def parse_directory(path: Path) -> Iterator[Conversation]:
    """Parse all JSON files in a directory, dispatching by content shape."""
    json_files = sorted(path.rglob("*.json"))
    for p in json_files:
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(1024)
            low = head.lower()
        except OSError:
            continue
        if '"mapping"' in low and '"author"' in low:
            yield from parse_chatgpt_file(p)
        elif '"chat_messages"' in low or '"chatMessages"' in low or '"sender"' in low:
            yield from parse_claude_file(p)
        elif '"gemini"' in low or '"myactivity"' in low or '"my activity"' in low:
            yield from parse_gemini_file(p)
        else:
            # Try each parser once; cheap fallback for unknown shapes.
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(data, list) and data and isinstance(data[0], dict) and ("mapping" in data[0] or "conversation_id" in data[0]):
                yield from parse_chatgpt_json(data, str(p))
            elif isinstance(data, dict) and ("chat_messages" in data or "messages" in data):
                yield from _parse_one_claude(data, str(p))

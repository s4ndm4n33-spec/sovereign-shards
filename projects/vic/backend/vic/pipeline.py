"""V.I.C. processing pipeline: ingest → parse → extract → preview.

A single :func:`process_inputs` call returns a serializable result struct
suitable for JSON responses. The Flask app in :mod:`app` wraps this.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .detect import detect_provider
from .extract import (
    extract_from_conversation,
    extract_themes,
    group_by_project,
    summarize,
    timeline,
)
from .models import Conversation
from .output import build_jsonl, build_pdf, parse_jsonl, PROVIDER_LABEL
from .parsers import (
    extract_conversations_from_zip,
    parse_chatgpt_file,
    parse_claude_file,
    parse_directory,
    parse_gemini_file,
)

log = logging.getLogger("vic.pipeline")


@dataclass
class ProcessResult:
    providers: list[str]
    session_count: int
    message_count: int
    date_range: tuple[str, str]
    themes: list[tuple[str, int]]
    projects: dict[str, list[dict]]
    sessions: list[dict]  # chronological, with extracted fields
    jsonl: str
    exec_summary: str = ""


def _parse_zip(zip_path: Path) -> list[Conversation]:
    """Parse a single ZIP archive, dispatching by provider markers."""
    providers = detect_provider(zip_path=zip_path)
    out: list[Conversation] = []
    if "chatgpt" in providers:
        out.extend(extract_conversations_from_zip(zip_path))
    if "gemini" in providers:
        # extract_conversations_from_zip also handles Gemini when conversations.json is absent
        if not out:
            out.extend(extract_conversations_from_zip(zip_path))
    if not out:
        # Last resort: treat as a generic archive of JSON files
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tdp)
            out.extend(parse_directory(tdp))
    return out


def _parse_files(paths: list[Path]) -> list[Conversation]:
    """Parse loose JSON files, dispatching by content shape."""
    out: list[Conversation] = []
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(1024).lower()
        except OSError:
            continue
        if '"mapping"' in head and '"author"' in head:
            out.extend(parse_chatgpt_file(p))
        elif '"chat_messages"' in head or '"chatmessages"' in head or '"sender"' in head or '"claude"' in head:
            out.extend(parse_claude_file(p))
        elif '"gemini"' in head or 'my activity' in head:
            out.extend(parse_gemini_file(p))
        else:
            # Try each parser once
            out.extend(parse_claude_file(p))
            if not out or not any(c.provider == "claude" for c in out[-3:]):
                out.extend(parse_chatgpt_file(p))
    return out


def process_inputs(zip_paths: list[Path], json_paths: list[Path]) -> ProcessResult:
    conversations: list[Conversation] = []

    for zp in zip_paths:
        try:
            conversations.extend(_parse_zip(zp))
        except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
            log.warning("Failed processing ZIP %s: %s", zp, exc)

    if json_paths:
        conversations.extend(_parse_files(json_paths))

    return process_conversations(conversations)


def process_conversations(conversations: list[Conversation]) -> ProcessResult:
    """Run the extract/build pipeline on a pre-built conversation list.

    Shared by file uploads and the URL crawler so both paths produce the
    same preview/export shape.
    """
    # De-duplicate by (provider, raw_id) when raw_id is present
    seen: set[tuple[str, str]] = set()
    deduped: list[Conversation] = []
    for c in conversations:
        key = (c.provider, c.raw_id)
        if c.raw_id and key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    conversations = deduped

    ordered = timeline(conversations)
    providers = sorted({c.provider for c in ordered if c.provider})
    themes = extract_themes(ordered)

    # Per-session preview payloads
    sessions: list[dict] = []
    for idx, conv in enumerate(ordered, start=1):
        ext = extract_from_conversation(conv)
        sessions.append({
            "session": idx,
            "date": conv.date_iso(),
            "provider": conv.provider,
            "provider_label": PROVIDER_LABEL.get(conv.provider, conv.provider.title()),
            "title": conv.title,
            "summary": summarize(conv),
            "decisions": ext["decisions"],
            "bugs": ext["bugs"],
            "fixes": ext["fixes"],
            "architecture": ext["architecture"],
            "open_questions": ext["open_questions"],
            "message_count": len(conv.messages),
        })

    # Project groupings (serialized)
    project_map = group_by_project(ordered)
    projects: dict[str, list[dict]] = {}
    for label, convs in project_map.items():
        projects[label] = [
            {
                "date": c.date_iso(),
                "provider": c.provider,
                "title": c.title,
                "summary": summarize(c, max_sentences=2),
            }
            for c in convs
        ]

    dates = [c.created for c in ordered if c.created] or [c.updated for c in ordered if c.updated]
    date_range = (
        (min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d")) if dates else ("unknown", "unknown")
    )

    jsonl_text = build_jsonl(ordered)
    total_msgs = sum(len(c.messages) for c in ordered)
    prov_labels = ", ".join(PROVIDER_LABEL.get(p, p.title()) for p in providers) or "none"
    theme_str = "; ".join(f"{t} ({n})" for t, n in themes[:6]) if themes else "none detected"
    exec_summary = (
        f"Archive spans {len(ordered)} conversations across {len(providers)} "
        f"provider(s): {prov_labels}. Date range: {date_range[0]} to {date_range[1]}. "
        f"Approximately {total_msgs} messages analyzed. "
        f"Recurring themes: {theme_str}."
    )

    return ProcessResult(
        providers=providers,
        session_count=len(ordered),
        message_count=total_msgs,
        date_range=date_range,
        themes=themes,
        projects=projects,
        sessions=sessions,
        jsonl=jsonl_text,
        exec_summary=exec_summary,
    )


def result_to_dict(result: ProcessResult) -> dict:
    d = asdict(result)
    return d


def make_pdf_bytes(result: ProcessResult, title: str) -> bytes:
    # Reconstruct minimal Conversation list isn't needed; reuse sessions
    from .models import Conversation, Message
    from datetime import datetime

    convs: list[Conversation] = []
    for s in result.sessions:
        c = Conversation(
            provider=s["provider"],
            source_file="",
            raw_id=str(s["session"]),
            title=s["title"],
            messages=[Message(role="user", content=s["summary"])] if s["summary"] else [],
        )
        if s["date"] and s["date"] != "unknown":
            try:
                c.created = datetime.strptime(s["date"], "%Y-%m-%d")
            except ValueError:
                pass
        convs.append(c)
    return build_pdf(convs, project_title=title)

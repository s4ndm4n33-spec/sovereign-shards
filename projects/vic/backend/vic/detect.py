"""Provider auto-detection from archive contents.

Detection is structural: it inspects file names and ZIP member paths
plus shallow JSON key signatures. It never executes user content.
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import Iterable

# Sentinel file names / fragments that identify each provider's export.
GEMINI_MARKERS = (
    "Takeout/",  # Google Takeout root
    "My Activity/Gemini",
    "Gemini/",
    "MyActivity/Gemini",
    "my_activity_gemini",
)

CHATGPT_MARKERS = (
    "conversations.json",
    "chat.html",
    "messages",
)

CLAUDE_MARKERS = (
    "claude",  # Claude projects export json files commonly named claude_*
    "conversations",  # claude exports use conversations/*.json or similar
)


def _zip_names(zip_path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            return [n for n in zf.namelist()]
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return []


def detect_provider(zip_path: Path | None = None, json_files: Iterable[Path] | None = None) -> set[str]:
    """Return the set of providers detected in the supplied inputs.

    A single archive may legitimately contain more than one provider
    (e.g. a folder mixing Claude JSON and a ChatGPT export ZIP).
    """
    detected: set[str] = set()

    names: list[str] = []
    if zip_path is not None:
        names.extend(os.path.basename(str(zip_path)).lower())
        names.extend(n.lower() for n in _zip_names(zip_path))

    files: list[str] = []
    if json_files:
        files.extend(str(p).lower() for p in json_files)
        for p in json_files:
            files.append(p.name.lower())

    haystack = names + files

    joined_names = " ".join(names)
    joined_files = " ".join(files)
    joined_all = " ".join(haystack)

    # GEMINI: Google Takeout structure or Gemini folders
    if any(m.lower() in joined_all for m in GEMINI_MARKERS):
        detected.add("gemini")

    # CHATGPT: conversations.json in archive or folder
    if "conversations.json" in joined_all:
        detected.add("chatgpt")
    elif zip_path is not None and _looks_like_chatgpt_zip(zip_path):
        detected.add("chatgpt")

    # CLAUDE: explicit claude markers or json files without chatgpt signature
    if any(m.lower() in joined_files for m in CLAUDE_MARKERS):
        detected.add("claude")

    # Fallback: inspect JSON content shallowly to disambiguate bare JSON files
    if json_files is not None and not detected:
        for p in json_files:
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    head = f.read(2048)
                if '"mapping"' in head or '"conversation_id"' in head or '"chatgpt"' in head.lower():
                    detected.add("chatgpt")
                    break
            except OSError:
                continue

    if not detected:
        detected.add("unknown")

    return detected


def _looks_like_chatgpt_zip(zip_path: Path) -> bool:
    names = _zip_names(zip_path)
    if not names:
        return False
    lower = " ".join(n.lower() for n in names)
    return "conversations.json" in lower or '"chatgpt"' in lower


def _peek_json(path: Path, n: int = 4096) -> dict | list | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(n)
        obj = json.loads(head)
        return obj
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    except OSError:
        return None

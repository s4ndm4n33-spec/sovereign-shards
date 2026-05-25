# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Path containment guard for tool scripts.

Every file-touching tool script must call safe_path() before opening,
writing, or creating anything.  This is the single enforcement point
that keeps the agent inside the project root regardless of what the
LLM passes as an argument.

Usage:
    from _path_guard import safe_path
    resolved = safe_path(user_supplied_path)  # raises SystemExit on escape
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Project root = three levels up from tools/run/
_ROOT: Path = Path(__file__).resolve().parent.parent.parent


def safe_path(raw: str, *, allow_create: bool = False) -> Path:
    """Resolve *raw* and verify it stays inside the project root.

    Args:
        raw: The path string received from the agent / CLI argument.
        allow_create: When False (default) the path must already exist.
                      When True the parent directory must exist inside root.

    Returns:
        Resolved absolute Path guaranteed to be within the project root.

    Raises:
        SystemExit(1): prints an error and exits if the path escapes root,
                       is an empty string, or (when allow_create=False) does
                       not exist.  Using SystemExit keeps the tool-script
                       interface consistent — callers see [PATH GUARD ERROR].
    """
    if not raw or not raw.strip():
        print("[PATH GUARD ERROR] Empty path rejected.")
        sys.exit(1)

    try:
        resolved = (_ROOT / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
    except Exception as exc:
        print(f"[PATH GUARD ERROR] Cannot resolve path {raw!r}: {exc}")
        sys.exit(1)

    # Containment check — covers ../, absolute, UNC, Windows drive-letter escapes
    try:
        resolved.relative_to(_ROOT)
    except ValueError:
        print(f"[PATH GUARD ERROR] Path escapes project root: {raw!r} → {resolved}")
        sys.exit(1)

    if not allow_create and not resolved.exists():
        print(f"[PATH GUARD ERROR] Path does not exist: {resolved}")
        sys.exit(1)

    return resolved

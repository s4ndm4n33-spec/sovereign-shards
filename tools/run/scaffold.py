# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Create a Python package directory with __init__.py inside the project root.

Usage: python scaffold.py <name>
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _path_guard import safe_path

name = sys.argv[1] if len(sys.argv) > 1 else ""
if not name:
    print("[SCAFFOLD ERROR] No package name provided.")
    sys.exit(1)

resolved = safe_path(name, allow_create=True)
resolved.mkdir(parents=True, exist_ok=True)

init = resolved / "__init__.py"
if not init.exists():
    init.write_text("", encoding="utf-8")

print(f"[SCAFFOLD OK] {resolved}")

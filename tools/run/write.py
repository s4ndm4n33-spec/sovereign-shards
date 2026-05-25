# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Write content to a file inside the project root.

Usage: python write.py <path> [content]
       If content is omitted it is read from stdin.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from _path_guard import safe_path

path_arg = sys.argv[1] if len(sys.argv) > 1 else ""
if len(sys.argv) > 2:
    data = sys.argv[2]
else:
    data = sys.stdin.read()

resolved = safe_path(path_arg, allow_create=True)

with open(resolved, "w", encoding="utf-8") as handle:
    handle.write(data)

print(f"[WRITE OK] {resolved}")

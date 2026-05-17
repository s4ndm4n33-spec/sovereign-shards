# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
import os
import sys


name = sys.argv[1]
os.makedirs(name, exist_ok=True)
with open(os.path.join(name, "__init__.py"), "w", encoding="utf-8") as handle:
    handle.write("")

print(f"[SCAFFOLD OK] {name}")

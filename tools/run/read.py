import os
import sys

# Force UTF-8 output to avoid cp1252 crashes on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

path = sys.argv[1]
if os.path.exists(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        print(handle.read())
else:
    print(f"[READ ERROR] File not found: {path}")

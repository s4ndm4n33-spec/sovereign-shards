# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""File integrity checker — SHA-256 hash verification for the shard.

Usage: python integrity.py [path] [--baseline]
  --baseline  Generate/update baseline hashes for all tracked files.
  (no flag)   Compare current hashes against saved baseline.

Baseline is stored at logs/integrity_baseline.json.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BASELINE_PATH = BASE_DIR / "logs" / "integrity_baseline.json"

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules",
             "logs", "memory", "models", "model-server", "Lib",
             "Scripts", "site-packages", "python"}
SKIP_EXT = {".pyc", ".pyo", ".pyd", ".exe", ".bin", ".dll", ".gguf", ".zip"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB — skip large binaries


def _sha256(path: str) -> str:
    """Compute SHA-256 hex digest."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan(root: str) -> dict[str, str]:
    """Scan tracked files and return {relative_path: sha256}."""
    root = os.path.abspath(root)
    hashes: dict[str, str] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in sorted(filenames):
            if any(fname.endswith(ext) for ext in SKIP_EXT):
                continue
            full = os.path.join(dirpath, fname)
            try:
                if os.path.getsize(full) > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                hashes[rel] = _sha256(full)
            except OSError:
                continue

    return hashes


def _save_baseline(hashes: dict[str, str]) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(BASELINE_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, sort_keys=True)
    os.replace(tmp, str(BASELINE_PATH))


def _load_baseline() -> dict[str, str] | None:
    if not BASELINE_PATH.exists():
        return None
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def main() -> None:
    root = str(BASE_DIR)
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        root = sys.argv[1]

    if "--baseline" in sys.argv:
        hashes = _scan(root)
        _save_baseline(hashes)
        print(f"[INTEGRITY] Baseline saved: {len(hashes)} files → {BASELINE_PATH}")
        return

    # Compare mode
    baseline = _load_baseline()
    if baseline is None:
        print("[INTEGRITY] No baseline found. Run with --baseline first.")
        return

    current = _scan(root)

    added = sorted(set(current) - set(baseline))
    removed = sorted(set(baseline) - set(current))
    modified = sorted(
        f for f in set(current) & set(baseline)
        if current[f] != baseline[f]
    )

    if not added and not removed and not modified:
        print(f"[INTEGRITY OK] All {len(baseline)} files match baseline.")
        return

    print("--- INTEGRITY REPORT ---")
    if modified:
        print(f"\n[MODIFIED] {len(modified)} file(s):")
        for f in modified:
            print(f"  ✎ {f}")
            print(f"    was: {baseline[f][:16]}...")
            print(f"    now: {current[f][:16]}...")
    if added:
        print(f"\n[ADDED] {len(added)} file(s):")
        for f in added:
            print(f"  + {f}")
    if removed:
        print(f"\n[REMOVED] {len(removed)} file(s):")
        for f in removed:
            print(f"  - {f}")

    total_issues = len(modified) + len(added) + len(removed)
    print(f"\n--- {total_issues} change(s) detected vs baseline ---")


if __name__ == "__main__":
    main()

# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Shard self-defence toolkit — SHIELD layer.

Subcommands:
  verify      — Check file integrity against baseline. Alert on tampering.
  baseline    — Generate fresh integrity baseline for core files.
  autorun     — Scan USB root for autorun.inf and remove it.
  wipe <path> — Secure-delete a file (overwrite with random bytes, then remove).

Usage:  python shield.py <subcommand> [args...]
"""

import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BASELINE_PATH = BASE_DIR / "logs" / "integrity_baseline.json"

# Directories that are NOT security-critical (skip during integrity checks)
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules",
             "logs", "memory", "models", "model-server", "Lib",
             "Scripts", "site-packages", "python"}
SKIP_EXT = {".pyc", ".pyo", ".pyd", ".exe", ".bin", ".dll", ".gguf", ".zip"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

# Core paths that MUST NOT change without detection
CORE_DIRS = ("app", "prompts", "tools")

# Wipe pass count — 3 passes is sufficient for flash media (USB)
WIPE_PASSES = 3


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan(root: str) -> dict[str, str]:
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


def cmd_baseline() -> None:
    hashes = _scan(str(BASE_DIR))
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(BASELINE_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, sort_keys=True)
    os.replace(tmp, str(BASELINE_PATH))
    print(f"[SHIELD] Baseline saved: {len(hashes)} files")


def cmd_verify() -> None:
    if not BASELINE_PATH.exists():
        print("[SHIELD] No baseline found. Run: run_shield baseline")
        return

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    current = _scan(str(BASE_DIR))

    added = sorted(set(current) - set(baseline))
    removed = sorted(set(baseline) - set(current))
    modified = sorted(
        f for f in set(current) & set(baseline)
        if current[f] != baseline[f]
    )

    # Flag core directory changes as CRITICAL
    critical = []
    for f in modified + added + removed:
        if any(f.startswith(d + "/") for d in CORE_DIRS):
            critical.append(f)

    if not added and not removed and not modified:
        print(f"[SHIELD OK] All {len(baseline)} files match baseline.")
        return

    print("--- SHIELD INTEGRITY REPORT ---")
    if critical:
        print(f"\n[CRITICAL] {len(critical)} core file(s) changed:")
        for f in critical:
            print(f"  !! {f}")

    if modified:
        print(f"\n[MODIFIED] {len(modified)} file(s):")
        for f in modified:
            sev = "CRITICAL" if f in critical else "INFO"
            print(f"  [{sev}] {f}")
    if added:
        print(f"\n[ADDED] {len(added)} file(s):")
        for f in added:
            print(f"  + {f}")
    if removed:
        print(f"\n[REMOVED] {len(removed)} file(s):")
        for f in removed:
            print(f"  - {f}")

    total = len(modified) + len(added) + len(removed)
    print(f"\n--- {total} change(s), {len(critical)} critical ---")


def cmd_autorun() -> None:
    """Check for autorun.inf at common mount points and shard root."""
    targets = [
        str(BASE_DIR / "autorun.inf"),
        str(BASE_DIR.parent / "autorun.inf"),  # USB root if shard is in subfolder
    ]
    # Also check drive root on Windows (e.g., E:\autorun.inf)
    drive = str(BASE_DIR)[:3]  # e.g., "E:\"
    if len(drive) == 3 and drive[1] == ":":
        targets.append(os.path.join(drive, "autorun.inf"))

    found = []
    for path in targets:
        if os.path.exists(path):
            found.append(path)
            try:
                os.remove(path)
                print(f"[SHIELD] REMOVED malicious autorun.inf: {path}")
            except OSError as e:
                print(f"[SHIELD] FOUND autorun.inf but cannot remove: {path} ({e})")

    if not found:
        print("[SHIELD] No autorun.inf found. Clean.")
    else:
        print(f"[SHIELD] {len(found)} autorun.inf file(s) neutralised.")


def cmd_wipe(path: str) -> None:
    """Secure-delete: overwrite with random bytes, then remove."""
    if not os.path.isfile(path):
        print(f"[SHIELD ERROR] File not found: {path}")
        return

    try:
        size = os.path.getsize(path)
        with open(path, "r+b") as f:
            for pass_num in range(WIPE_PASSES):
                f.seek(0)
                f.write(secrets.token_bytes(size))
                f.flush()
                os.fsync(f.fileno())
        os.remove(path)
        print(f"[SHIELD] Secure-wiped: {path} ({size} bytes, {WIPE_PASSES} passes)")
    except OSError as e:
        print(f"[SHIELD ERROR] Wipe failed: {e}")


def main() -> None:
    if len(sys.argv) < 2:
        print("[SHIELD] Subcommands: verify, baseline, autorun, wipe <path>")
        return

    sub = sys.argv[1].lower()
    if sub == "verify":
        cmd_verify()
    elif sub == "baseline":
        cmd_baseline()
    elif sub == "autorun":
        cmd_autorun()
    elif sub == "wipe":
        if len(sys.argv) < 3:
            print("[SHIELD ERROR] Usage: run_shield wipe <path>")
            return
        cmd_wipe(sys.argv[2])
    else:
        print(f"[SHIELD ERROR] Unknown subcommand: {sub}")


if __name__ == "__main__":
    main()

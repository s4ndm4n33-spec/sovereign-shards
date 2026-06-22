"""End-to-end smoke test for V.I.C.

Generates synthetic conversation archives for all three providers,
runs the full pipeline, asserts the result shape, and writes sample
PDF + JSONL outputs to a temp dir. Run: python3 tests/test_pipeline.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

# allow `from vic import ...` resolution
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vic.pipeline import process_inputs, result_to_dict, make_pdf_bytes  # noqa: E402

BASE_TS = datetime(2026, 3, 14, 9, 0, 0)


def make_chatgpt_export() -> bytes:
    """Sample conversations.json payload."""
    data = [
        {
            "id": "c1",
            "title": "Build VIC arch decisions",
            "create_time": BASE_TS.timestamp(),
            "update_time": (BASE_TS + timedelta(hours=1)).timestamp(),
            "mapping": _mapping([
                ("user", "We decided to use Flask for the backend of VIC."),
                ("assistant", "Good choice. I'd avoid anything heavier."),
                ("user", "There's a bug in the parser — it crashes on nested JSON. Should we refactor?"),
                ("assistant", "Fixed it by validating types before parsing. The architecture now separates detect and parse layers."),
            ]),
        },
        {
            "id": "c2",
            "title": "VIC frontend tailwind theme",
            "create_time": (BASE_TS + timedelta(days=2)).timestamp(),
            "update_time": (BASE_TS + timedelta(days=2, hours=1)).timestamp(),
            "mapping": _mapping([
                ("user", "We decided on a dark theme with cyan accents."),
                ("assistant", "Sounds clean. Tailwind setup with custom color ramps."),
                ("user", "Open question: should we support streaming progress updates?"),
                ("assistant", "Performance is fine with XHR upload progress."),
            ]),
        },
    ]
    return json.dumps(data).encode("utf-8")


def _mapping(turns):
    """Build a fake ChatGPT mapping DAG from (role, content) tuples."""
    mapping = {}
    root_id = "root"
    mapping[root_id] = {"parent": None, "children": []}
    prev = root_id
    for i, (role, content) in enumerate(turns):
        nid = f"n{i}"
        mapping[nid] = {
            "parent": prev,
            "children": [],
            "message": {
                "id": nid,
                "author": {"role": role},
                "content": {"parts": [content]},
                "create_time": BASE_TS.timestamp() + i * 30,
            },
        }
        mapping[prev]["children"].append(nid)
        prev = nid
    return mapping


def make_claude_files(tmpdir: Path) -> list[Path]:
    files = []
    f1 = tmpdir / "claude_session_1.json"
    f1.write_text(json.dumps({
        "id": "cl-1",
        "title": "Memory module refactor",
        "created_at": (BASE_TS + timedelta(days=4)).isoformat(),
        "updated_at": (BASE_TS + timedelta(days=4, hours=2)).isoformat(),
        "chat_messages": [
            {"sender": "human", "text": "We decided to migrate the memory module to a class-based contract."},
            {"sender": "assistant", "text": "That's cleaner. I refactored the interface and corrected the retention bug."},
            {"sender": "human", "text": "Should we keep backwards-compatible shims?"},
        ],
    }))
    files.append(f1)
    f2 = tmpdir / "claude_session_2.json"
    f2.write_text(json.dumps({
        "id": "cl-2",
        "title": "Agent runtime errors",
        "created_at": (BASE_TS + timedelta(days=6)).isoformat(),
        "chat_messages": [
            {"sender": "human", "text": "The agent crashed with a deadlock error in the executor."},
            {"sender": "assistant", "text": "Resolved by adding an async timeout guard."},
            {"sender": "human", "text": "Let's stick with the modular architecture we chose earlier."},
        ],
    }))
    files.append(f2)
    return files


def make_gemini_takeout_zip(path: Path):
    data = {
        "events": [
            {
                "time": (BASE_TS + timedelta(days=1, hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "title": "How do I structure a Flask REST API for bulk processing?",
                "subtitles": [{"name": "Gemini", "text": "Use-blueprints-with-a-detect-layer"}],
            },
            {
                "time": (BASE_TS + timedelta(days=1, hours=2, minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "title": "What's the difference between Takeout ZIP folders?",
                "subtitles": [{"name": "Gemini", "text": "Takeout groups by product; Gemini lives under My Activity"}],
            },
            {
                "time": (BASE_TS + timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "title": "Decided to ship without authentication — sovereign by design choice.",
            },
        ]
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Takeout/My Activity/Gemini/MyActivity.json", json.dumps(data))
        zf.writestr("Takeout/about.html", "<html><body>Takeout sample</body></html>")


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="vic-test-"))
    # ChatGPT ZIP (single conversations.json inside)
    chatgpt_zip = tmpdir / "chatgpt.zip"
    with zipfile.ZipFile(chatgpt_zip, "w") as zf:
        zf.writestr("conversations.json", make_chatgpt_export())
    # Gemini Takeout ZIP
    gemini_zip = tmpdir / "gemini_takeout.zip"
    make_gemini_takeout_zip(gemini_zip)
    # Claude folder of JSON
    claude_dir = tmpdir / "claude_export"
    claude_dir.mkdir()
    claude_files = make_claude_files(claude_dir)

    result = process_inputs([chatgpt_zip, gemini_zip], claude_files)

    assert result.session_count > 0, "No conversations parsed"
    assert set(result.providers) == {"chatgpt", "gemini", "claude"}, f"Providers: {result.providers}"
    assert result.jsonl, "JSONL empty"
    assert result.themes, "No themes extracted"
    print(f"Sessions: {result.session_count}")
    print(f"Providers: {result.providers}")
    print(f"Date range: {result.date_range}")
    print(f"Themes (top 3): {result.themes[:3]}")
    # Sanity: at least one decision extracted
    any_decision = any(s["decisions"] for s in result.sessions)
    assert any_decision, "No decisions extracted from any session"
    any_bug = any(s["bugs"] for s in result.sessions)
    assert any_bug, "No bugs extracted"
    any_fix = any(s["fixes"] for s in result.sessions)
    assert any_fix, "No fixes extracted"

    # Write artifacts to verify PDF and JSONL are produced.
    out_dir = tmpdir / "out"
    out_dir.mkdir()
    (out_dir / "archive.jsonl").write_text(result.jsonl, encoding="utf-8")
    pdf_bytes = make_pdf_bytes(result, "VIC Smoke Test")
    (out_dir / "VIC-report.pdf").write_bytes(pdf_bytes)
    assert pdf_bytes[:4] == b"%PDF", "PDF header missing"

    print(f"Artifacts written to: {out_dir}")
    print(f"  archive.jsonl: {len(result.jsonl)} bytes")
    print(f"  VIC-report.pdf: {len(pdf_bytes)} bytes")
    print("PASS — pipeline end-to-end with all three providers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""HTTP-level smoke test: hit /api/process, /api/pdf, /api/jsonl via test client."""

import io
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vic.app import app  # noqa: E402

BASE_TS = datetime(2026, 3, 14, 9, 0, 0)


def _mapping(turns):
    mapping = {"root": {"parent": None, "children": []}}
    prev = "root"
    for i, (role, content) in enumerate(turns):
        nid = f"n{i}"
        mapping[nid] = {
            "parent": prev,
            "children": [],
            "message": {
                "author": {"role": role},
                "content": {"parts": [content]},
                "create_time": BASE_TS.timestamp() + i * 30,
            },
        }
        mapping[prev]["children"].append(nid)
        prev = nid
    return mapping


def main() -> int:
    chatgpt_data = [
        {"id": "c1", "title": "VIC arch", "create_time": BASE_TS.timestamp(), "mapping": _mapping([
            ("user", "We decided to use Flask for the backend."),
            ("assistant", "Good. There's a bug — fix it with a guard."),
        ])}
    ]
    chatgpt_zip_buf = io.BytesIO()
    with zipfile.ZipFile(chatgpt_zip_buf, "w") as zf:
        zf.writestr("conversations.json", json.dumps(chatgpt_data))

    claude_json = json.dumps({
        "id": "cl-1",
        "title": "Memory refactor",
        "created_at": (BASE_TS + timedelta(days=2)).isoformat(),
        "chat_messages": [
            {"sender": "human", "text": "We decided to migrate memory to a class."},
            {"sender": "assistant", "text": "Resolved the deadlock by adding a guard."},
        ],
    }).encode("utf-8")

    client = app.test_client()
    data = {
        "files": [
            (io.BytesIO(chatgpt_zip_buf.getvalue()), "chatgpt.zip"),
            (io.BytesIO(claude_json), "claude.json"),
        ]
    }
    r = client.post("/api/process", data=data, content_type="multipart/form-data")
    assert r.status_code == 200, f"process failed: {r.status_code} {r.data[:300]}"
    body = r.get_json()
    assert body["providers"], f"no providers: {body}"
    assert body["session_count"] > 0, "no sessions"
    assert body["jsonl"], "no jsonl"
    jsonl_entries = [json.loads(l) for l in body["jsonl"].splitlines() if l]
    assert all(["session" in e and "summary" in e for e in jsonl_entries]), "bad jsonl shape"

    # PDF round-trip
    r = client.post("/api/pdf", json={
        "title": "HTTP Smoke Test",
        "sessions": body["sessions"],
        "providers": body["providers"],
        "exec_summary": body["exec_summary"],
        "themes": body["themes"],
    })
    assert r.status_code == 200, f"pdf failed: {r.status_code} {r.data[:300]}"
    assert r.data[:4] == b"%PDF", "PDF header missing"

    # JSONL round-trip
    r = client.post("/api/jsonl", json={"jsonl": body["jsonl"]})
    assert r.status_code == 200, f"jsonl failed: {r.status_code} {r.data[:300]}"
    assert b"session" in r.data

    print(f"PASS — {body['session_count']} sessions, providers={body['providers']}")
    print(f"  themes={body['themes'][:3]}")
    print(f"  pdf={len(r.data)} bytes (last response)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

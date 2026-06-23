"""End-to-end historian test.

Ingests:
  - The V.I.C. backend git history (its own submodule) — uses a temp git repo
  - A sample markdown ADR
  - Structured notes (decisions + milestones)
  - Chat conversations (ChatGPT + Claude)

Then verifies:
  - Store stats reflect ingested data
  - Timeline engine returns linked events
  - Semantic search returns relevant results
  - Narrative generation produces executive summary, arch evolution, decision tree
  - Historical question answering ("who introduced…") works
"""

import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vic.store import Store
from vic.ingest import ingest_git, ingest_markdown, ingest_structured_notes, ingest_conversations
from vic.timeline import build_timeline, answer_question
from vic.narrator import (
    generate_executive_summary,
    generate_architectural_evolution,
    generate_decision_tree,
    generate_from_query,
)
from vic.models import Conversation, Message


def _make_git_repo(tmpdir: Path) -> Path:
    """Create a tiny git repo with a few commits to test ingestion."""
    repo = tmpdir / "sample-repo"
    repo.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "Alice Dev", "GIT_AUTHOR_EMAIL": "alice@example.com",
           "GIT_COMMITTER_NAME": "Alice Dev", "GIT_COMMITTER_EMAIL": "alice@example.com"}
    subprocess.check_call(["git", "init"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.check_call(["git", "config", "user.name", "Alice Dev"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "alice@example.com"], cwd=repo)
    # Commit 1
    (repo / "README.md").write_text("# Sample Repo\nA test project for V.I.C.\n")
    subprocess.check_call(["git", "add", "."], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "feat: initial commit with README"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    # Commit 2
    (repo / "parser.py").write_text("def parse():\n    pass\n")
    subprocess.check_call(["git", "add", "."], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "feat(parser): add parser skeleton"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    # Commit 3
    env2 = {**env, "GIT_AUTHOR_NAME": "Bob Eng", "GIT_AUTHOR_EMAIL": "bob@example.com",
            "GIT_COMMITTER_NAME": "Bob Eng", "GIT_COMMITTER_EMAIL": "bob@example.com"}
    (repo / "parser.py").write_text("def parse():\n    # fixed bug with nested json\n    import json\n    pass\n")
    subprocess.check_call(["git", "add", "."], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "fix(parser): handle nested JSON without crashing"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env2)
    # Commit 4
    subprocess.check_call(["git", "checkout", "-b", "feature/registry"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (repo / "registry.py").write_text("class Registry:\n    pass\n")
    subprocess.check_call(["git", "add", "."], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "feat(registry): introduce backend registry pattern"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env2)
    return repo


def _make_adr(tmpdir: Path) -> Path:
    p = tmpdir / "adr-001-flask.md"
    p.write_text("""---
title: ADR-001 Use Flask for backend
date: 2026-03-15
author: Alice Dev
tags: [decision, architecture]
scope: backend
---

# ADR-001: Use Flask for the backend

## Context
We need a Python backend for V.I.C.

## Decision
We decided to use Flask. It's lightweight and well-understood.

## Status
Accepted.
""")
    return p


def _make_notes(tmpdir: Path) -> Path:
    p = tmpdir / "notes.json"
    p.write_text(json.dumps({
        "decisions": [
            {"title": "Adopt registry pattern for backends", "date": "2026-04-01", "rationale": "Decouple runtime from backend kernels", "status": "accepted", "scope": "runtime", "tags": ["architecture", "registry"]},
        ],
        "milestones": [
            {"name": "v0.1 Alpha", "achieved_at": "2026-04-15", "kind": "release", "description": "First internal alpha"},
            {"name": "JGPU integration", "achieved_at": "2026-05-20", "kind": "milestone", "description": "Distributed tensor runtime wired in"},
        ],
    }))
    return p


def _make_chats() -> list[Conversation]:
    return [
        Conversation(
            provider="chatgpt", source_file="conv1.json", raw_id="c1",
            title="Discuss registry pattern",
            created=datetime(2026, 3, 28),
            messages=[
                Message(role="user", content="We decided to introduce the registry pattern for backend kernels.", timestamp=datetime(2026, 3, 28, 10)),
                Message(role="assistant", content="Good. The registry decouples runtime from backend kernels and lets us add CUDA/Metal later."),
            ],
        ),
        Conversation(
            provider="claude", source_file="conv2.json", raw_id="c2",
            title="JGPU architecture discussion",
            created=datetime(2026, 5, 18),
            messages=[
                Message(role="user", content="When did we first discuss JGPU? Let's plan the integration."),
                Message(role="assistant", content="JGPU was first mentioned in March. We should refactor the runtime to accept distributed backends."),
            ],
        ),
    ]


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="vic-hist-"))
    db_path = tmpdir / "test.db"
    store = Store(path=db_path)

    # 1. Git ingestion
    repo = _make_git_repo(tmpdir)
    r = ingest_git(store, repo, repo_id="sample-repo")
    assert r["commits"] >= 3, f"Expected >=3 commits, got {r}"
    print(f"Git: {r['commits']} commits ingested")

    # 2. Markdown ADR ingestion
    adr = _make_adr(tmpdir)
    r = ingest_markdown(store, adr, repo_id="sample-repo")
    assert r.get("decision"), "ADR should be detected as a decision"
    print(f"Markdown: {r['title']} (decision={r['decision']})")

    # 3. Structured notes
    notes = _make_notes(tmpdir)
    r = ingest_structured_notes(store, notes, repo_id="sample-repo")
    assert r["notes"] >= 2, f"Expected >=2 notes, got {r}"
    print(f"Notes: {r['notes']} items ingested")

    # 4. Chat conversations
    chats = _make_chats()
    r = ingest_conversations(store, chats, repo_id="sample-repo")
    assert r["sessions"] >= 2 and r["events"] >= 4
    print(f"Chats: {r['sessions']} sessions, {r['events']} message events")

    # 5. Verify stats
    stats = store.stats()
    assert stats["events"] > 0, "No events in store"
    assert stats["repositories"] >= 1
    assert stats["decisions"] >= 1
    print(f"Stats: {stats['events']} events, {stats['decisions']} decisions, {stats['persons']} persons, {stats['artifacts']} artifacts")

    # 6. Timeline
    tl = build_timeline(store, repository_id="sample-repo")
    assert tl["events"], "Timeline should have events"
    assert tl["links"], "Timeline should have links between events"
    assert tl["clusters"], "Timeline should produce clusters"
    print(f"Timeline: {len(tl['events'])} events, {len(tl['links'])} links, {len(tl['clusters'])} clusters")

    # 7. Semantic search
    results = store.search_semantic("registry pattern backend", repository_id="sample-repo")
    assert results, "Semantic search should find results for 'registry pattern'"
    top_title = (results[0].get("title") or "").lower()
    assert "registry" in top_title or "registry" in (results[0].get("body") or "").lower(), f"Top result should mention registry: {results[0].get('title')}"
    print(f"Search 'registry pattern': top result = {results[0].get('title')[:60]}")

    # 8. Narrative generation
    summary = generate_executive_summary(store, repository_id="sample-repo")
    assert "Executive Summary" in summary.body
    assert len(summary.event_ids) > 0
    print(f"Narrative (executive summary): {len(summary.event_ids)} cited events")

    arch = generate_architectural_evolution(store, repository_id="sample-repo")
    assert "Architectural Evolution" in arch.body
    print(f"Narrative (arch evolution): {len(arch.event_ids)} cited events")

    tree = generate_decision_tree(store, repository_id="sample-repo")
    assert "Decision Tree" in tree.body
    print(f"Narrative (decision tree): {len(tree.event_ids)} decisions")

    # 9. Historical Q&A
    answer = answer_question(store, "Who introduced the registry pattern?", repository_id="sample-repo")
    assert answer["events"], "Should find events for registry pattern question"
    print(f"Q 'Who introduced registry?': {answer['answer'][:100]}")

    answer2 = answer_question(store, "When did we first discuss JGPU?", repository_id="sample-repo")
    assert answer2["events"], "Should find events mentioning JGPU"
    print(f"Q 'When did we first discuss JGPU?': {answer2['answer'][:100]}")

    # 10. Query-based narrative
    narr = generate_from_query(store, "Why did the runtime architecture change between March and June?", repository_id="sample-repo")
    assert "Query:" in narr.body
    print(f"Query narrative: {len(narr.event_ids)} supporting events")

    print("\nPASS — historian pipeline end-to-end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""End-to-end V2 test: Knowledge Graph, Biography, Evolution, Provenance.

Ingests sample data (git commits, ADRs, notes, chats) via V1 ingestion,
then verifies V2 capabilities:
  - KnowledgeGraph builds with inferred typed edges
  - Biography generation with evidence chains
  - Evolution queries (reversed decisions, churn, impact)
  - Provenance queries return evidence
  - No V1 regressions
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vic.store import Store
from vic.ingest import ingest_git, ingest_markdown, ingest_structured_notes, ingest_conversations
from vic.knowledge_graph import KnowledgeGraph
from vic.biography import generate_biography
from vic.evolution import (
    reversed_decisions, architectural_churn, discussed_not_implemented,
    conversations_to_code, decision_impact, top_contributors,
)
from vic.graph_model import Edge, EdgeType
from vic.models import Conversation, Message


def _make_git_repo(tmpdir: Path) -> Path:
    repo = tmpdir / "v2-repo"
    repo.mkdir()
    env_a = {**os.environ, "GIT_AUTHOR_NAME": "Alice", "GIT_AUTHOR_EMAIL": "alice@example.com",
             "GIT_COMMITTER_NAME": "Alice", "GIT_COMMITTER_EMAIL": "alice@example.com"}
    subprocess.check_call(["git", "init"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.check_call(["git", "config", "user.name", "Alice"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "alice@example.com"], cwd=repo)

    (repo / "README.md").write_text("# V2 Test\n")
    subprocess.check_call(["git", "add", "."], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "feat: initial commit"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env_a)

    (repo / "registry.py").write_text("class Registry:\n    pass\n")
    subprocess.check_call(["git", "add", "."], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "feat(registry): introduce registry pattern for plugins"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env_a)

    (repo / "parser.py").write_text("def parse():\n    import json\n    pass\n")
    subprocess.check_call(["git", "add", "."], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "refactor(parser): restructure for architecture module"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env_a)

    return repo


def _make_adr(tmpdir: Path) -> Path:
    p = tmpdir / "adr.md"
    p.write_text("""---
title: Adopt registry pattern
date: 2026-03-15
author: Alice
tags: [decision, architecture]
scope: runtime
---

# ADR: Adopt registry pattern

## Context
We need plugin discovery.

## Decision
We decided to use the registry pattern for backend plugins.

## Status
Accepted.
""")
    return p


def _make_notes(tmpdir: Path) -> Path:
    p = tmpdir / "notes.json"
    p.write_text(json.dumps({
        "decisions": [
            {"title": "Use Flask for backend", "date": "2026-03-01", "rationale": "Lightweight", "status": "superseded", "scope": "backend", "tags": ["decision", "architecture"]},
            {"title": "Use FastAPI for backend", "date": "2026-05-01", "rationale": "Better async support", "status": "accepted", "scope": "backend", "tags": ["decision", "architecture"]},
        ],
        "milestones": [
            {"name": "v0.1", "achieved_at": "2026-04-01", "kind": "release"},
        ],
    }))
    return p


def _make_chats() -> list[Conversation]:
    return [
        Conversation(
            provider="chatgpt", source_file="c1.json", raw_id="c1",
            title="Registry pattern discussion",
            created=datetime(2026, 3, 10),
            messages=[
                Message(role="user", content="We decided to use the registry pattern for plugin discovery.", timestamp=datetime(2026, 3, 10, 10)),
                Message(role="assistant", content="The registry pattern will decouple the runtime from backends. Good architecture choice."),
            ],
        ),
        Conversation(
            provider="claude", source_file="c2.json", raw_id="c2",
            title="JGPU planning",
            created=datetime(2026, 5, 15),
            messages=[
                Message(role="user", content="When did we first discuss JGPU? We need a distributed tensor runtime."),
                Message(role="assistant", content="JGPU was first mentioned in March. We should add a distributed backend layer."),
            ],
        ),
    ]


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="vic-v2-"))
    store = Store(path=tmpdir / "test.db")
    repo_id = "v2-test"

    # Ingest
    repo = _make_git_repo(tmpdir)
    r_git = ingest_git(store, repo, repo_id=repo_id)
    assert r_git["commits"] >= 3, f"Git: {r_git}"

    r_md = ingest_markdown(store, _make_adr(tmpdir), repo_id=repo_id)
    assert r_md.get("decision"), "ADR should detect decision"

    r_notes = ingest_structured_notes(store, _make_notes(tmpdir), repo_id=repo_id)
    assert r_notes["notes"] >= 2, f"Notes: {r_notes}"

    r_chat = ingest_conversations(store, _make_chats(), repo_id=repo_id)
    assert r_chat["sessions"] >= 2

    stats = store.stats()
    print(f"Stats: {stats['events']} events, {stats['decisions']} decisions, {stats['edges']} edges")

    # 1. Knowledge Graph builds with inferred edges
    kg = KnowledgeGraph(store, repository_id=repo_id)
    assert kg.nodes, "Graph should have nodes"
    assert kg.edges, "Graph should have edges"
    inferred = sum(1 for e in kg.edges if e.confidence < 1.0)
    assert inferred > 0, "Should have inferred edges"
    edge_types = kg.edge_type_counts()
    print(f"Graph: {len(kg.nodes)} nodes, {len(kg.edges)} edges ({inferred} inferred)")
    print(f"  Edge types: {edge_types}")

    # Check for IMPLEMENTS edges (commit → decision with "registry" keywords)
    implements_edges = [e for e in kg.edges if e.relationship_type == EdgeType.IMPLEMENTS.value]
    assert implements_edges, "Should infer IMPLEMENTS edges for commits matching decisions"
    print(f"  IMPLEMENTS: {len(implements_edges)} edges")

    # Check for DISCUSSES edges (chat → decision)
    discusses_edges = [e for e in kg.edges if e.relationship_type == EdgeType.DISCUSSES.value]
    assert discusses_edges, "Should infer DISCUSSES edges for chats mentioning decisions"
    print(f"  DISCUSSES: {len(discusses_edges)} edges")

    # Check SUPERSEDES (Flask → FastAPI)
    supersedes_edges = [e for e in kg.edges if e.relationship_type == EdgeType.SUPERSEDES.value]
    assert supersedes_edges, "Should infer SUPERSEDES between Flask and FastAPI decisions"
    print(f"  SUPERSEDES: {len(supersedes_edges)} edges")

    # 2. Biography generation with provenance
    bio = generate_biography(kg, "registry pattern", repository_id=repo_id)
    assert bio["found"], "Biography for 'registry pattern' should find events"
    assert bio["stats"]["total_mentions"] > 0
    assert bio["claims"], "Biography should have claims with evidence"
    # Verify provenance: claims have evidence event IDs
    for claim in bio["claims"]:
        assert claim["confidence"] > 0, "Claims should have confidence > 0"
        if claim["evidence"]:
            assert all("event_id" in ev for ev in claim["evidence"]), "Evidence should have event_ids"
    print(f"Biography 'registry pattern': {bio['stats']['total_mentions']} mentions, {len(bio['claims'])} claims, status={bio['current_status']}")

    # Check JGPU biography
    bio_jgpu = generate_biography(kg, "JGPU", repository_id=repo_id)
    assert bio_jgpu["found"], "JGPU biography should find events"
    assert bio_jgpu["first_mention"]["origin"] in ("chatgpt", "claude"), "JGPU should originate from a chat"
    print(f"Biography 'JGPU': first={bio_jgpu['first_mention']['date']}, origin={bio_jgpu['first_mention']['origin']}, status={bio_jgpu['current_status']}")

    # 3. Evolution queries
    rev = reversed_decisions(kg, repo_id)
    assert rev["count"] > 0, "Should find reversed/superseded decisions (Flask was superseded)"
    assert rev["claims"], "Reversed decisions should have claims"
    print(f"Evolution [reversed_decisions]: {rev['count']} results")

    churn = architectural_churn(kg, repo_id)
    assert churn["results"], "Should find areas with churn"
    print(f"Evolution [churn]: {churn['count']} areas, top={churn['results'][0]['area']} score={churn['results'][0]['churn_score']}")

    dni = discussed_not_implemented(kg, repo_id)
    # JGPU should be discussed but not implemented (no commit mentions JGPU)
    print(f"Evolution [discussed_not_implemented]: {dni['count']} concepts")

    c2c = conversations_to_code(kg, repo_id)
    # Registry pattern was discussed in chat → decision exists → commit implements it
    assert c2c["count"] > 0, "Should find conversations that led to code"
    print(f"Evolution [conversations_to_code]: {c2c['count']} chains")

    impact = decision_impact(kg, repo_id, min_downstream=1)
    assert impact["results"], "Should find decisions with downstream impact"
    print(f"Evolution [decision_impact]: {impact['count']} decisions, top downstream={impact['results'][0]['downstream_count']}")

    contribs = top_contributors(kg, repo_id)
    assert contribs["results"], "Should find contributors"
    print(f"Evolution [top_contributors]: {contribs['count']} contributors, top={contribs['results'][0]['name']}")

    # 4. Provenance — verify evidence chains are traceable
    if c2c["results"]:
        conv = c2c["results"][0]
        # The chain: chat → decision → commit
        assert conv["decision_id"], "Should have decision_id"
        assert conv["implementing_commits"], "Should have implementing commits"

    # 5. Explicit edge persistence works
    test_edge = Edge(
        source_node=list(kg.nodes.keys())[0],
        target_node=list(kg.nodes.keys())[-1],
        relationship_type=EdgeType.REFERENCES.value,
        confidence=0.99,
        rationale="Manual test edge",
        provenance=["test"],
    )
    store.upsert_edge(test_edge)
    stored = store.list_edges(relationship_type=EdgeType.REFERENCES.value)
    assert any(e["id"] == test_edge.id for e in stored), "Explicit edge should persist"
    print(f"Explicit edge persistence: OK")

    print("\nPASS — V2 knowledge graph, biography, evolution, provenance end-to-end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

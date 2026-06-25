"""Concept biography generator — the life story of any concept.

Phase 4 — Concept Biographies:
  Given a concept name (e.g. "JGPU", "registry pattern"), find every
  event, decision, commit, and conversation mentioning it, then compose
  a structured biography with first mention, origin, first decision,
  first implementation, major pivots, current status, contributors,
  and an evidence chain with confidence scores.

Biographies are generated dynamically — nothing is manually authored.
Every claim cites supporting event IDs.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from .graph_model import Claim
from .knowledge_graph import KnowledgeGraph
from .store import Store

log = logging.getLogger("vic.biography")


def _fmt(s: Optional[str]) -> str:
    if not s:
        return "unknown"
    return s[:10]


def generate_biography(kg: KnowledgeGraph, concept: str, repository_id: Optional[str] = None) -> dict:
    """Generate a structured biography for a concept."""
    store = kg.store
    concept_lower = concept.lower()

    # 1. Find all events mentioning the concept (semantic + literal)
    sem = store.search_semantic(concept, repository_id=repository_id, limit=50)
    all_events = store.list_events(repository_id=repository_id, limit=10000)
    literal = [e for e in all_events if concept_lower in ((e.get("title") or "") + " " + (e.get("body") or "")).lower()]

    seen_ids: set[str] = set()
    events: list[dict] = []
    for e in sem + literal:
        if e["id"] not in seen_ids:
            seen_ids.add(e["id"])
            events.append(e)
    events.sort(key=lambda e: e.get("occurred_at") or "")

    if not events:
        return {"concept": concept, "found": False, "message": f"No events mention '{concept}'."}

    # 2. Classify events
    decisions = [e for e in events if e.get("kind") == "decision"]
    commits = [e for e in events if e.get("kind") == "commit"]
    chats = [e for e in events if e.get("kind") in ("chat_message", "chat_session")]
    docs = [e for e in events if e.get("kind") in ("doc_created", "doc_edit")]
    releases = [e for e in events if e.get("kind") in ("release", "milestone")]

    first = events[0]
    first_kind = first.get("kind", "unknown")
    origin_source = first.get("source_kind", "unknown")

    # 3. Cross-reference with graph edges
    event_ids = set(e["id"] for e in events)
    related: list[dict] = []
    for eid in event_ids:
        for n in kg.neighbors(eid):
            if n["id"] not in event_ids:
                related.append(n)
        for n in kg.incoming(eid):
            if n["id"] not in event_ids:
                related.append(n)
    seen_rel: set[str] = set()
    deduped: list[dict] = []
    for r in related:
        if r["id"] not in seen_rel:
            seen_rel.add(r["id"])
            deduped.append(r)
    deduped.sort(key=lambda e: e.get("occurred_at") or "")

    # 4. Current status
    current_status = _determine_status(events, decisions)

    # 5. Pivots
    pivots = [e for e in events if e.get("kind") == "decision"
              and any(w in (e.get("body") or "").lower() for w in ("supersed", "reject", "reverse", "pivot"))]
    for d in decisions:
        for rev in kg.incoming(d["id"], "reverses"):
            pivots.append(rev)

    # 6. Contributors
    actor_counts: dict[str, int] = {}
    for e in events:
        aid = e.get("actor_id") or "unknown"
        actor_counts[aid] = actor_counts.get(aid, 0) + 1
    persons = store.list_persons(repository_id=repository_id)
    pmap = {p["id"]: p.get("name") or p.get("username") or p.get("email") or p["id"] for p in persons}
    contributors = sorted(
        [{"name": pmap.get(a, a), "contributions": c} for a, c in actor_counts.items()],
        key=lambda c: -c["contributions"],
    )

    # 7. Claims with evidence chains
    claims: list[Claim] = []
    if first:
        claims.append(Claim(
            subject=concept, predicate="was_first_mentioned_on", obj=_fmt(first.get("occurred_at")),
            evidence=[_ev(first)], confidence=0.9, inference_rule="earliest_event_mention",
        ))
    if commits:
        claims.append(Claim(
            subject=concept, predicate="was_first_implemented_in", obj=(commits[0].get("title") or "")[:80],
            evidence=[_ev(commits[0])], confidence=0.85, inference_rule="earliest_commit_mention",
        ))
    if chats and not commits:
        claims.append(Claim(
            subject=concept, predicate="was_discussed_but_not_implemented_as_of", obj=_fmt(events[-1].get("occurred_at")),
            evidence=[_ev(chats[0])], confidence=0.7, inference_rule="no_implementation_found",
        ))
    if decisions:
        claims.append(Claim(
            subject=concept, predicate="has_related_decisions", obj=str(len(decisions)),
            evidence=[_ev(d) for d in decisions[:5]], confidence=0.95, inference_rule="decision_count",
        ))

    # 8. Biography narrative
    lines: list[str] = [f"# {concept}", ""]
    lines.append(f"**First Mention:** {_fmt(first.get('occurred_at'))}")
    lines.append(f"**Origin:** {origin_source} ({first_kind.replace('_', ' ')})")
    if decisions:
        lines.append(f"**First Decision:** {_fmt(decisions[0].get('occurred_at'))}")
    if commits:
        lines.append(f"**First Implementation:** {_fmt(commits[0].get('occurred_at'))}")
    lines.append(f"**Current Status:** {current_status}")
    lines.append("")
    lines.append(f"**Related Decisions:** {len(decisions)}")
    lines.append(f"**Related Commits:** {len(commits)}")
    lines.append(f"**Related Conversations:** {len(chats)}")
    lines.append(f"**Related Documents:** {len(docs)}")
    if pivots:
        lines.append(f"**Major Pivots:** {len(pivots)}")
    lines.append("")
    if contributors:
        lines.append("**Primary Contributors:**")
        for c in contributors[:5]:
            lines.append(f"  - {c['name']} ({c['contributions']})")
    lines.append("\n## Timeline of Mentions")
    for e in events[:30]:
        lines.append(f"- **{_fmt(e.get('occurred_at'))}** [{e.get('kind','').replace('_',' ')}] {e.get('title','')}")
    lines.append("\n## Evidence Chain")
    for c in claims:
        lines.append(f"\n**Claim:** {c.subject} {c.predicate} {c.obj}")
        lines.append(f"**Confidence:** {c.confidence:.2f}")
        lines.append(f"**Inference rule:** {c.inference_rule}")
        lines.append("**Evidence:**")
        for ev in c.evidence:
            lines.append(f"  - {_fmt(ev.get('occurred_at'))} [{ev.get('source_kind','')}] {ev.get('title','')}")

    return {
        "concept": concept,
        "found": True,
        "biography": "\n".join(lines),
        "first_mention": {"date": _fmt(first.get("occurred_at")), "origin": origin_source, "kind": first_kind, "event_id": first["id"], "title": first.get("title", "")},
        "first_decision": {"date": _fmt(decisions[0].get("occurred_at")), "event_id": decisions[0]["id"], "title": decisions[0].get("title", "")} if decisions else None,
        "first_implementation": {"date": _fmt(commits[0].get("occurred_at")), "event_id": commits[0]["id"], "title": commits[0].get("title", "")} if commits else None,
        "current_status": current_status,
        "stats": {
            "total_mentions": len(events), "decisions": len(decisions), "commits": len(commits),
            "conversations": len(chats), "documents": len(docs), "releases": len(releases),
            "pivots": len(pivots), "graph_related": len(deduped),
        },
        "contributors": contributors[:10],
        "claims": [c.to_dict() for c in claims],
        "timeline": [{"date": _fmt(e.get("occurred_at")), "kind": e.get("kind", ""), "title": e.get("title", ""), "event_id": e["id"]} for e in events[:50]],
        "graph_related": [{"date": _fmt(r.get("occurred_at")), "relation": r.get("_edge_type", ""), "title": r.get("title", ""), "event_id": r["id"]} for r in deduped[:20]],
    }


def _ev(e: dict) -> dict:
    return {"event_id": e["id"], "title": e.get("title", ""), "occurred_at": e.get("occurred_at"), "source_kind": e.get("source_kind", "")}


def _determine_status(events: list[dict], decisions: list[dict]) -> str:
    if not events:
        return "unknown"
    for d in decisions:
        body = (d.get("body") or "").lower()
        if "superseded" in body or "deprecated" in body:
            return "deprecated/superseded"
        if "rejected" in body:
            return "rejected"
    has_commits = any(e.get("kind") == "commit" for e in events)
    has_chats = any(e.get("kind") in ("chat_message", "chat_session") for e in events)
    if has_commits and has_chats:
        return "active"
    if has_commits:
        return "implemented"
    if has_chats:
        return "discussed"
    return "mentioned"

"""Evolution Engine — architectural reasoning over the knowledge graph.

Phase 5 — Evolution Engine:
  Answers research questions (not documentation questions):

  - reversed_decisions:     "Show me every design decision that was later reversed."
  - architectural_churn:    "Which modules have accumulated the most architectural churn?"
  - discussed_not_implemented: "What ideas have been discussed repeatedly but never implemented?"
  - conversations_to_code: "Which conversations resulted in implemented code?"
  - decision_impact:       "Which decisions had the greatest downstream impact?"
  - top_contributors:      "Who are the most influential contributors?"

These operate over the typed graph, not SQLite directly. Each result
carries a Claim with an evidence chain so the reasoning is traceable.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

from .graph_model import Claim, EdgeType
from .knowledge_graph import KnowledgeGraph, _keywords
from .store import Store

log = logging.getLogger("vic.evolution")


def reversed_decisions(kg: KnowledgeGraph, repository_id: Optional[str] = None) -> dict:
    """Find every design decision that was later reversed or superseded."""
    store = kg.store
    decisions = store.list_decisions(repository_id=repository_id)
    d_event = {e["detail_id"]: e["id"] for e in kg.nodes.values() if e.get("kind") == "decision" and e.get("detail_id")}

    results: list[dict] = []
    claims: list[Claim] = []

    for d in decisions:
        if d.get("status") not in ("superseded", "rejected", "deprecated"):
            continue
        eid = d_event.get(d["id"], "")
        evidence: list[dict] = []

        for r in kg.incoming(eid, EdgeType.REVERSES.value):
            evidence.append({"event_id": r["id"], "title": r.get("title", ""), "occurred_at": r.get("occurred_at"), "source_kind": r.get("source_kind", "")})
        for s in kg.incoming(eid, EdgeType.SUPERSEDES.value):
            evidence.append({"event_id": s["id"], "title": f"Superseded by: {s.get('title', '')}", "occurred_at": s.get("occurred_at"), "source_kind": "supersession"})

        if not evidence:
            evidence.append({"event_id": eid, "title": f"Decision status: {d.get('status', '')}", "occurred_at": d.get("decided_at"), "source_kind": "decision_status"})

        claims.append(Claim(
            subject=d.get("title", ""), predicate="was_reversed_by",
            obj=d.get("superseded_by") or "subsequent events",
            evidence=evidence, confidence=0.95 if len(evidence) > 1 else 0.8,
            inference_rule="reverses_or_supersedes_edge",
        ))
        results.append({
            "decision_id": d["id"], "title": d.get("title", ""), "status": d.get("status", ""),
            "scope": d.get("scope", ""), "decided_at": d.get("decided_at"),
            "superseded_by": d.get("superseded_by"), "evidence": evidence,
        })

    return {"query": "reversed_decisions", "count": len(results), "results": results, "claims": [c.to_dict() for c in claims]}


def architectural_churn(kg: KnowledgeGraph, repository_id: Optional[str] = None) -> dict:
    """Find modules/areas with the most architectural churn."""
    events = list(kg.nodes.values())
    area_events: dict[str, list[dict]] = defaultdict(list)

    for e in events:
        tags = e.get("tags") or []
        for t in tags:
            if t in ("refactor", "architecture", "breaking", "revert"):
                area = _identify_area(e)
                area_events[area].append(e)
        if e.get("kind") == "decision":
            area_events[_identify_area(e)].append(e)

    decisions = kg.store.list_decisions(repository_id=repository_id)
    for d in decisions:
        area = d.get("scope") or _area_from_kw(d.get("title", ""))
        area_events[area].append({
            "id": d["id"], "kind": "decision", "title": d.get("title", ""),
            "occurred_at": d.get("decided_at"), "tags": d.get("tags", []),
            "importance": 0.85, "body": d.get("rationale", ""),
        })

    ranked: list[dict] = []
    claims: list[Claim] = []
    for area, evts in area_events.items():
        if not evts:
            continue
        breaking = sum(1 for e in evts if "breaking" in (e.get("tags") or []))
        refactor = sum(1 for e in evts if "refactor" in (e.get("tags") or []))
        dec_count = sum(1 for e in evts if e.get("kind") == "decision")
        score = len(evts) + (breaking * 3) + (refactor * 2) + (dec_count * 1.5)
        ranked.append({
            "area": area, "event_count": len(evts), "breaking_changes": breaking,
            "refactors": refactor, "decisions": dec_count, "churn_score": round(score, 1),
            "latest_event": max((e.get("occurred_at") or "" for e in evts), default=""),
        })
        if score > 5:
            claims.append(Claim(
                subject=area, predicate="has_high_architectural_churn",
                obj=f"score {score:.1f} across {len(evts)} events",
                evidence=[{"event_id": e.get("id", ""), "title": e.get("title", ""), "occurred_at": e.get("occurred_at")} for e in evts[:5]],
                confidence=min(0.95, 0.5 + score / 20), inference_rule="churn_score_threshold",
            ))

    ranked.sort(key=lambda x: -x["churn_score"])
    return {"query": "architectural_churn", "count": len(ranked), "results": ranked[:20], "claims": [c.to_dict() for c in claims[:10]]}


def discussed_not_implemented(kg: KnowledgeGraph, repository_id: Optional[str] = None) -> dict:
    """Find concepts discussed in conversations but never implemented."""
    chat_events = [e for e in kg.nodes.values() if e.get("kind") in ("chat_message", "chat_session")]
    commit_events = [e for e in kg.nodes.values() if e.get("kind") == "commit"]

    chat_concepts: dict[str, list[dict]] = defaultdict(list)
    seen_concepts: set[str] = set()

    for chat in chat_events:
        text = (chat.get("title", "") + " " + (chat.get("body") or "")).lower()
        for m in re.finditer(r"\b([a-z][a-z0-9_-]{2,})\s+(?:pattern|module|architecture|runtime|engine|layer|service)\b", text):
            seen_concepts.add(m.group(1))

    for concept in seen_concepts:
        for chat in chat_events:
            text = (chat.get("title", "") + " " + (chat.get("body") or "")).lower()
            if concept in text:
                chat_concepts[concept].append(chat)

    unimplemented: list[dict] = []
    claims: list[Claim] = []
    implemented_count = 0

    for concept, chats in chat_concepts.items():
        in_commit = any(concept in ((c.get("title") or "") + " " + (c.get("body") or "")).lower() for c in commit_events)
        if in_commit:
            implemented_count += 1
            continue
        unimplemented.append({
            "concept": concept, "discussion_count": len(chats),
            "first_discussed": min((c.get("occurred_at") or "" for c in chats), default=""),
            "last_discussed": max((c.get("occurred_at") or "" for c in chats), default=""),
            "evidence": [{"event_id": c["id"], "title": c.get("title", ""), "occurred_at": c.get("occurred_at")} for c in chats[:3]],
        })
        claims.append(Claim(
            subject=concept, predicate="was_discussed_but_never_implemented",
            obj=f"mentioned in {len(chats)} conversation(s)",
            evidence=[{"event_id": c["id"], "title": c.get("title", ""), "occurred_at": c.get("occurred_at"), "source_kind": c.get("source_kind", "")} for c in chats[:3]],
            confidence=0.75, inference_rule="no_matching_commit_found",
        ))

    unimplemented.sort(key=lambda x: -x["discussion_count"])
    return {"query": "discussed_not_implemented", "count": len(unimplemented), "results": unimplemented[:20], "implemented_count": implemented_count, "claims": [c.to_dict() for c in claims[:10]]}


def conversations_to_code(kg: KnowledgeGraph, repository_id: Optional[str] = None) -> dict:
    """Find which conversations resulted in implemented code."""
    results: list[dict] = []
    claims: list[Claim] = []

    for node in kg.nodes.values():
        if node.get("kind") not in ("chat_message", "chat_session"):
            continue
        discussed = kg.neighbors(node["id"], EdgeType.DISCUSSES.value)
        for dec in discussed:
            implementers = kg.incoming(dec["id"], EdgeType.IMPLEMENTS.value)
            if implementers:
                results.append({
                    "conversation_id": node["id"], "conversation_title": node.get("title", "")[:100],
                    "conversation_date": node.get("occurred_at"),
                    "decision_id": dec["id"], "decision_title": dec.get("title", "")[:100],
                    "implementing_commits": [{"commit_id": c["id"], "title": c.get("title", ""), "date": c.get("occurred_at")} for c in implementers[:5]],
                })
                claims.append(Claim(
                    subject=node.get("title", "")[:80], predicate="resulted_in_implementation",
                    obj=f"{len(implementers)} commit(s)",
                    evidence=[
                        {"event_id": node["id"], "title": node.get("title", ""), "occurred_at": node.get("occurred_at"), "source_kind": node.get("source_kind", "")},
                        {"event_id": dec["id"], "title": dec.get("title", ""), "occurred_at": dec.get("occurred_at"), "source_kind": "decision"},
                        *[{"event_id": c["id"], "title": c.get("title", ""), "occurred_at": c.get("occurred_at"), "source_kind": "git"} for c in implementers[:3]],
                    ],
                    confidence=0.9, inference_rule="discusses_to_implements_chain",
                ))

    return {"query": "conversations_to_code", "count": len(results), "results": results[:20], "claims": [c.to_dict() for c in claims[:10]]}


def decision_impact(kg: KnowledgeGraph, repository_id: Optional[str] = None, min_downstream: int = 2) -> dict:
    """Find decisions with the greatest downstream impact."""
    decision_events = [e for e in kg.nodes.values() if e.get("kind") == "decision"]
    results: list[dict] = []
    claims: list[Claim] = []

    for d in decision_events:
        # Traverse both outgoing AND incoming edges for downstream impact:
        # a decision is "implemented" by commits (incoming IMPLEMENTS),
        # "discussed" by chats (incoming DISCUSSES), etc.
        reachable = kg.reachable(d["id"], max_depth=3,
                                  follow_types={EdgeType.IMPLEMENTS.value, EdgeType.CONTAINS.value, EdgeType.DEPENDS_ON.value, EdgeType.RESOLVES.value, EdgeType.DISCUSSES.value, EdgeType.DOCUMENTS.value, EdgeType.REFERENCES.value})
        # Also include nodes that point TO this decision
        for edge in kg._reverse.get(d["id"], []):
            if edge.relationship_type in {EdgeType.IMPLEMENTS.value, EdgeType.DISCUSSES.value, EdgeType.DOCUMENTS.value, EdgeType.REFERENCES.value}:
                reachable.add(edge.source_node)
                # Go one more hop from the source
                for edge2 in kg._adjacency.get(edge.source_node, []):
                    reachable.add(edge2.target_node)
        downstream = reachable - {d["id"]}
        if len(downstream) >= min_downstream:
            down_events = [kg.nodes[did] for did in downstream if did in kg.nodes]
            kind_counts: dict[str, int] = defaultdict(int)
            for e in down_events:
                kind_counts[e.get("kind", "unknown")] += 1
            results.append({
                "decision_id": d["id"], "title": d.get("title", "")[:100],
                "occurred_at": d.get("occurred_at"), "downstream_count": len(downstream),
                "downstream_kinds": dict(kind_counts),
            })
            claims.append(Claim(
                subject=d.get("title", "")[:80], predicate="had_downstream_impact_on",
                obj=f"{len(downstream)} subsequent events",
                evidence=[{"event_id": d["id"], "title": d.get("title", ""), "occurred_at": d.get("occurred_at"), "source_kind": "decision"},
                          *[{"event_id": e["id"], "title": e.get("title", ""), "occurred_at": e.get("occurred_at"), "source_kind": e.get("source_kind", "")} for e in down_events[:5]]],
                confidence=min(0.95, 0.5 + len(downstream) * 0.05),
                inference_rule="transitive_closure_depth_3",
            ))

    results.sort(key=lambda x: -x["downstream_count"])
    return {"query": "decision_impact", "count": len(results), "results": results[:20], "claims": [c.to_dict() for c in claims[:10]]}


def top_contributors(kg: KnowledgeGraph, repository_id: Optional[str] = None) -> dict:
    """Find the most influential contributors by event count + importance."""
    actor_events: dict[str, list[dict]] = defaultdict(list)
    for e in kg.nodes.values():
        if e.get("actor_id"):
            actor_events[e["actor_id"]].append(e)

    persons = kg.store.list_persons(repository_id=repository_id)
    pmap = {p["id"]: p for p in persons}

    results: list[dict] = []
    claims: list[Claim] = []

    for aid, evts in actor_events.items():
        if aid == "unknown" or not evts:
            continue
        p = pmap.get(aid, {})
        name = p.get("name") or p.get("username") or p.get("email") or aid
        avg_importance = sum(e.get("importance", 0.5) for e in evts) / len(evts)
        score = len(evts) * avg_importance
        kinds: dict[str, int] = defaultdict(int)
        for e in evts:
            kinds[e.get("kind", "unknown")] += 1
        results.append({
            "actor_id": aid, "name": name, "event_count": len(evts),
            "avg_importance": round(avg_importance, 2), "influence_score": round(score, 1),
            "kinds": dict(kinds),
        })
        if score > 3:
            claims.append(Claim(
                subject=name, predicate="is_a_top_contributor",
                obj=f"{len(evts)} events, influence {score:.1f}",
                evidence=[{"event_id": e["id"], "title": e.get("title", ""), "occurred_at": e.get("occurred_at"), "source_kind": e.get("source_kind", "")} for e in sorted(evts, key=lambda x: -(x.get("importance") or 0))[:5]],
                confidence=min(0.95, 0.4 + score / 20), inference_rule="weighted_event_count",
            ))

    results.sort(key=lambda x: -x["influence_score"])
    return {"query": "top_contributors", "count": len(results), "results": results[:20], "claims": [c.to_dict() for c in claims[:10]]}


def run_evolution_query(kg: KnowledgeGraph, query: str, repository_id: Optional[str] = None) -> dict:
    """Dispatch a natural-language evolution query."""
    q = query.lower().strip()
    if "reversed" in q or "supersed" in q:
        return reversed_decisions(kg, repository_id)
    if "churn" in q:
        return architectural_churn(kg, repository_id)
    if "discussed" in q and ("never" in q or "not implemented" in q):
        return discussed_not_implemented(kg, repository_id)
    if "conversation" in q and ("implement" in q or "code" in q):
        return conversations_to_code(kg, repository_id)
    if "impact" in q or "downstream" in q:
        return decision_impact(kg, repository_id)
    if "contributor" in q or "influential" in q:
        return top_contributors(kg, repository_id)
    return {
        "query": query,
        "results": {
            "reversed_decisions": reversed_decisions(kg, repository_id),
            "architectural_churn": architectural_churn(kg, repository_id),
            "discussed_not_implemented": discussed_not_implemented(kg, repository_id),
            "conversations_to_code": conversations_to_code(kg, repository_id),
            "decision_impact": decision_impact(kg, repository_id),
            "top_contributors": top_contributors(kg, repository_id),
        },
    }


def _identify_area(event: dict) -> str:
    m = re.match(r"^[a-z]+\(([^)]+)\)", event.get("title") or "")
    if m:
        return m.group(1).lower()
    tags = event.get("tags") or []
    for t in tags:
        if t not in ("feat", "fix", "refactor", "chore", "docs", "test", "breaking", "merge"):
            return t.lower()
    return "general"


def _area_from_kw(text: str) -> str:
    kws = _keywords(text)
    return list(kws)[0] if kws else "general"

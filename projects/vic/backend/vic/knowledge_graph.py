"""Knowledge Graph builder for V.I.C.

Builds a typed knowledge graph from store events and decisions.
Infers typed edges (IMPLEMENTS, DISCUSSES, SUPERSEDES, etc.) using
deterministic keyword matching. Every inferred edge carries a
confidence < 1.0 and a rationale string.

The graph is the foundation for biography generation, evolution
queries, and provenance tracing.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from .graph_model import Edge, EdgeType
from .store import Store

log = logging.getLogger("vic.knowledge_graph")


def _keywords(text: str) -> set[str]:
    """Extract significant keywords from text (for matching)."""
    _STOP = set(
        "the a an and or but if then else for to of in on at by with from as is it "
        "this that these those i you he she we they me him her us them my your his "
        "hers our their was were been being have has had do does did will would "
        "should could may might can shall not no nor".split()
    )
    _TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
    tokens = _TOKEN_RE.findall(text.lower())
    return {t for t in tokens if t not in _STOP and len(t) > 2}


class KnowledgeGraph:
    """Typed knowledge graph built from store events + decisions.

    Nodes are event dicts keyed by event ID. Edges are Edge objects
    (from graph_model.py) with typed relationship_type, confidence,
    rationale, and provenance.
    """

    def __init__(self, store: Store, repository_id: Optional[str] = None):
        self.store = store
        self.repository_id = repository_id
        self.nodes: Dict[str, dict] = {}
        self.edges: List[Edge] = []
        self._adjacency: Dict[str, List[Edge]] = defaultdict(list)
        self._reverse: Dict[str, List[Edge]] = defaultdict(list)
        self._build()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        events = self.store.list_events(repository_id=self.repository_id, limit=10000)
        for e in events:
            eid = e["id"]
            node = dict(e)
            node.setdefault("kind", e.get("kind", "unknown"))
            node.setdefault("tags", e.get("tags") or [])
            node.setdefault("importance", e.get("importance") or 0.5)
            self.nodes[eid] = node

        # Load explicit edges from store
        stored_edges = self.store.list_edges()
        for se in stored_edges:
            edge = Edge(
                source_node=se["source_node"],
                target_node=se["target_node"],
                relationship_type=se["relationship_type"],
                confidence=se.get("confidence", 1.0),
                rationale=se.get("rationale", ""),
                provenance=(se.get("provenance") or []),
                created_at=se.get("created_at", ""),
            )
            self._add_edge(edge)

        # Infer typed edges
        self._infer_implements()
        self._infer_discusses()
        self._infer_supersedes()
        self._infer_precedes()
        self._infer_contains()

    def _add_edge(self, edge: Edge) -> None:
        # Deduplicate by (source, target, type)
        for existing in self._adjacency.get(edge.source_node, []):
            if existing.target_node == edge.target_node and existing.relationship_type == edge.relationship_type:
                return
        self.edges.append(edge)
        self._adjacency[edge.source_node].append(edge)
        self._reverse[edge.target_node].append(edge)

    # ------------------------------------------------------------------
    # Edge inference rules
    # ------------------------------------------------------------------

    def _infer_implements(self) -> None:
        """Infer IMPLEMENTS edges: commits that match decision keywords."""
        decisions = [e for e in self.nodes.values() if e.get("kind") == "decision"]
        commits = [e for e in self.nodes.values() if e.get("kind") == "commit"]

        for dec in decisions:
            dec_kw = _keywords((dec.get("title") or "") + " " + (dec.get("body") or ""))
            if not dec_kw:
                continue
            for commit in commits:
                commit_kw = _keywords((commit.get("title") or "") + " " + (commit.get("body") or ""))
                overlap = dec_kw & commit_kw
                if len(overlap) >= 2:
                    confidence = min(0.9, 0.5 + len(overlap) * 0.1)
                    self._add_edge(Edge(
                        source_node=commit["id"],
                        target_node=dec["id"],
                        relationship_type=EdgeType.IMPLEMENTS.value,
                        confidence=confidence,
                        rationale=f"Keyword overlap: {', '.join(sorted(overlap)[:5])}",
                        provenance=[commit["id"], dec["id"]],
                    ))

    def _infer_discusses(self) -> None:
        """Infer DISCUSSES edges: chats that mention decision keywords."""
        decisions = [e for e in self.nodes.values() if e.get("kind") == "decision"]
        chats = [e for e in self.nodes.values() if e.get("kind") in ("chat_message", "chat_session")]

        for dec in decisions:
            dec_kw = _keywords((dec.get("title") or "") + " " + (dec.get("body") or ""))
            if not dec_kw:
                continue
            for chat in chats:
                chat_kw = _keywords((chat.get("title") or "") + " " + (chat.get("body") or ""))
                overlap = dec_kw & chat_kw
                if len(overlap) >= 2:
                    confidence = min(0.85, 0.45 + len(overlap) * 0.1)
                    self._add_edge(Edge(
                        source_node=chat["id"],
                        target_node=dec["id"],
                        relationship_type=EdgeType.DISCUSSES.value,
                        confidence=confidence,
                        rationale=f"Chat mentions decision keywords: {', '.join(sorted(overlap)[:5])}",
                        provenance=[chat["id"], dec["id"]],
                    ))

    def _infer_supersedes(self) -> None:
        """Infer SUPERSEDES edges between decisions.

        Two strategies:
        1. Explicit: decision has status='superseded' and superseded_by set.
        2. Implicit: two decisions share the same scope, one is 'superseded'
           and the other is 'accepted' — infer that the accepted one supersedes
           the superseded one.
        """
        decisions_raw = self.store.list_decisions(repository_id=self.repository_id)
        dec_events = {e.get("detail_id"): e["id"] for e in self.nodes.values()
                      if e.get("kind") == "decision" and e.get("detail_id")}

        # Strategy 1: explicit superseded_by
        for d in decisions_raw:
            if d.get("status") == "superseded" and d.get("superseded_by"):
                old_eid = dec_events.get(d["id"], "")
                new_eid = dec_events.get(d.get("superseded_by"), "")
                if old_eid and new_eid and old_eid in self.nodes and new_eid in self.nodes:
                    self._add_edge(Edge(
                        source_node=new_eid,
                        target_node=old_eid,
                        relationship_type=EdgeType.SUPERSEDES.value,
                        confidence=0.95,
                        rationale=f"Decision status: superseded by {d.get('superseded_by')}",
                        provenance=[d["id"], d.get("superseded_by", "")],
                    ))

        # Strategy 2: implicit by scope + status
        by_scope: dict[str, list[dict]] = defaultdict(list)
        for d in decisions_raw:
            scope = d.get("scope") or "general"
            by_scope[scope].append(d)

        for scope, decs in by_scope.items():
            superseded = [d for d in decs if d.get("status") == "superseded"]
            accepted = [d for d in decs if d.get("status") == "accepted"]
            for old in superseded:
                old_eid = dec_events.get(old["id"], "")
                if not old_eid or old_eid not in self.nodes:
                    continue
                for new in accepted:
                    new_eid = dec_events.get(new["id"], "")
                    if not new_eid or new_eid not in self.nodes or new_eid == old_eid:
                        continue
                    self._add_edge(Edge(
                        source_node=new_eid,
                        target_node=old_eid,
                        relationship_type=EdgeType.SUPERSEDES.value,
                        confidence=0.8,
                        rationale=f"Same scope '{scope}': '{new.get('title','')}' supersedes '{old.get('title','')}'",
                        provenance=[old["id"], new["id"]],
                    ))

    def _infer_precedes(self) -> None:
        """Infer PRECEDES edges: events that occur before related events."""
        events_by_time = sorted(self.nodes.values(), key=lambda e: e.get("occurred_at") or "")
        for i, e in enumerate(events_by_time):
            for j in range(i + 1, min(i + 5, len(events_by_time))):
                later = events_by_time[j]
                if e.get("id") == later.get("id"):
                    continue
                # Only link if they share tags or keywords
                shared_tags = set(e.get("tags") or []) & set(later.get("tags") or [])
                if shared_tags:
                    self._add_edge(Edge(
                        source_node=e["id"],
                        target_node=later["id"],
                        relationship_type=EdgeType.PRECEDES.value,
                        confidence=0.6,
                        rationale=f"Temporal precedence with shared tags: {', '.join(sorted(shared_tags)[:3])}",
                        provenance=[e["id"], later["id"]],
                    ))

    def _infer_contains(self) -> None:
        """Infer CONTAINS edges: sessions contain chat messages."""
        sessions = [e for e in self.nodes.values() if e.get("kind") == "chat_session"]
        messages = [e for e in self.nodes.values() if e.get("kind") == "chat_message"]

        for session in sessions:
            session_ref = session.get("source_ref", "")
            for msg in messages:
                msg_ref = msg.get("source_ref", "")
                if session_ref and msg_ref and session_ref == msg_ref:
                    self._add_edge(Edge(
                        source_node=session["id"],
                        target_node=msg["id"],
                        relationship_type=EdgeType.CONTAINS.value,
                        confidence=1.0,
                        rationale="Session contains message (same source_ref)",
                        provenance=[session["id"], msg["id"]],
                    ))

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def neighbors(self, node_id: str, edge_type: Optional[str] = None) -> List[dict]:
        """Return outgoing neighbor nodes, optionally filtered by edge type."""
        result: list[dict] = []
        for edge in self._adjacency.get(node_id, []):
            if edge_type and edge.relationship_type != edge_type:
                continue
            target = self.nodes.get(edge.target_node)
            if target:
                enriched = dict(target)
                enriched["_edge_type"] = edge.relationship_type
                enriched["_confidence"] = edge.confidence
                enriched["_rationale"] = edge.rationale
                result.append(enriched)
        return result

    def incoming(self, node_id: str, edge_type: Optional[str] = None) -> List[dict]:
        """Return incoming neighbor nodes, optionally filtered by edge type."""
        result: list[dict] = []
        for edge in self._reverse.get(node_id, []):
            if edge_type and edge.relationship_type != edge_type:
                continue
            source = self.nodes.get(edge.source_node)
            if source:
                enriched = dict(source)
                enriched["_edge_type"] = edge.relationship_type
                enriched["_confidence"] = edge.confidence
                enriched["_rationale"] = edge.rationale
                result.append(enriched)
        return result

    def reachable(self, node_id: str, max_depth: int = 3,
                  follow_types: Optional[Set[str]] = None) -> Set[str]:
        """BFS traversal from node_id, returning reachable node IDs."""
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(node_id, 0)]
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            for edge in self._adjacency.get(current, []):
                if follow_types and edge.relationship_type not in follow_types:
                    continue
                if edge.target_node not in visited:
                    queue.append((edge.target_node, depth + 1))
            for edge in self._reverse.get(current, []):
                if follow_types and edge.relationship_type not in follow_types:
                    continue
                if edge.source_node not in visited:
                    queue.append((edge.source_node, depth + 1))
        visited.discard(node_id)
        return visited

    def edge_type_counts(self) -> Dict[str, int]:
        """Return a count of edges by relationship type."""
        counts: dict[str, int] = defaultdict(int)
        for e in self.edges:
            counts[e.relationship_type] += 1
        return dict(counts)

    def to_dict(self) -> dict:
        """Serialize graph stats to a JSON-safe dict."""
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "edge_types": self.edge_type_counts(),
            "inferred_edges": sum(1 for e in self.edges if e.confidence < 1.0),
        }

    # ------------------------------------------------------------------
    # Legacy intent-reducer API (for ingestion_adapter compatibility)
    # ------------------------------------------------------------------

    def apply(self, intents: List[Dict[str, Any]]) -> None:
        """Apply a list of graph intents (ADD_NODE, ADD_EDGE, etc.)."""
        for intent in intents:
            op = intent.get("op")
            if op == "ADD_NODE":
                node = intent.get("node", {})
                node_id = node.get("entity_id")
                if node_id:
                    self.nodes[node_id] = node
            elif op == "ADD_EDGE":
                src = intent.get("from")
                dst = intent.get("to")
                rel = intent.get("relation")
                if src and dst and rel:
                    self._add_edge(Edge(
                        source_node=src,
                        target_node=dst,
                        relationship_type=rel,
                        confidence=1.0,
                        rationale="Explicit intent",
                        provenance=[intent.get("provenance", {}).get("source", "intent")],
                    ))
            elif op == "UPDATE_NODE":
                node = intent.get("node", {})
                node_id = node.get("entity_id")
                if node_id and node_id in self.nodes:
                    self.nodes[node_id].update(node)
            elif op == "DELETE_NODE":
                node_id = intent.get("node", {}).get("entity_id")
                if node_id and node_id in self.nodes:
                    del self.nodes[node_id]
                    self.edges = [e for e in self.edges
                                  if e.source_node != node_id and e.target_node != node_id]

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.nodes.get(node_id)

    def get_edges(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.edges]

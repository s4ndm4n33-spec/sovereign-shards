"""Knowledge Graph — in-memory typed graph above the SQLite store.

Phase 2 — Knowledge Graph:
  SQLite remains persistence only. The graph is an in-memory read model
  built from Events + stored Typed Edges + inferred edges.

Architecture::

    SQLite (events, edges, decisions, artifacts, …)
            ↓  rebuild()
    KnowledgeGraph (in-memory: nodes + typed edges + adjacency)
            ↓
    Timeline Engine · Narrative Engine · Evolution Engine · Search

Inferred edges carry confidence < 1.0 and a rationale explaining the
inference rule. Explicit edges from the store have confidence 1.0.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

from .graph_model import Edge, EdgeType
from .store import Store

log = logging.getLogger("vic.graph")

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_STOP = set(
    "the a an and or but if then else for to of in on at by with from as is it "
    "this that these those i you he she we they me him her us them my your his "
    "hers our their was were".split()
)


def _keywords(text: str, top_k: int = 15) -> set[str]:
    tokens = [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]
    return set(tokens[:top_k])


class KnowledgeGraph:
    """In-memory typed graph built from the SQLite store."""

    def __init__(self, store: Store, repository_id: Optional[str] = None):
        self.store = store
        self.repository_id = repository_id
        self.nodes: dict[str, dict] = {}
        self.edges: list[Edge] = []
        self._adjacency: dict[str, list[Edge]] = defaultdict(list)
        self._reverse: dict[str, list[Edge]] = defaultdict(list)
        self._decisions: list[dict] = []
        self.rebuild()

    # -- construction --------------------------------------------------------

    def rebuild(self) -> None:
        self.nodes.clear()
        self.edges.clear()
        self._adjacency.clear()
        self._reverse.clear()

        events = self.store.list_events(repository_id=self.repository_id, limit=10000)
        self._decisions = self.store.list_decisions(repository_id=self.repository_id)

        for e in events:
            self.nodes[e["id"]] = e

        # 1. Load explicit edges from store
        for row in self.store.list_edges():
            edge = Edge(
                source_node=row["source_node"], target_node=row["target_node"],
                relationship_type=row["relationship_type"], confidence=row["confidence"],
                rationale=row.get("rationale", ""), provenance=row.get("provenance", []),
                created_at=row.get("created_at", ""),
            )
            self._add_edge(edge)

        # 2. Infer edges
        self._infer_implements(events)
        self._infer_discusses(events)
        self._infer_documents(events)
        self._infer_contains(events)
        self._infer_supersedes()
        self._infer_reverses(events)
        self._infer_precedes(events)

        inferred = sum(1 for e in self.edges if e.confidence < 1.0)
        log.info("KnowledgeGraph: %d nodes, %d edges (%d inferred)", len(self.nodes), len(self.edges), inferred)

    def _add_edge(self, edge: Edge) -> None:
        existing = [e for e in self._adjacency.get(edge.source_node, [])
                    if e.target_node == edge.target_node and e.relationship_type == edge.relationship_type]
        if existing:
            if edge.confidence > existing[0].confidence:
                self.edges.remove(existing[0])
                self._adjacency[edge.source_node].remove(existing[0])
                self._reverse[edge.target_node].remove(existing[0])
            else:
                return
        self.edges.append(edge)
        self._adjacency[edge.source_node].append(edge)
        self._reverse[edge.target_node].append(edge)

    # -- edge inference -------------------------------------------------------

    def _decision_event_map(self) -> dict[str, str]:
        """Map decision detail_id → event_id for decision events."""
        m: dict[str, str] = {}
        for e in self.nodes.values():
            if e.get("kind") == "decision" and e.get("detail_id"):
                m[e["detail_id"]] = e["id"]
        return m

    def _decision_keywords(self) -> dict[str, set[str]]:
        m: dict[str, set[str]] = {}
        for d in self._decisions:
            kw = _keywords(d.get("title", "") + " " + d.get("rationale", ""))
            if kw:
                m[d["id"]] = kw
        return m

    def _infer_implements(self, events: list[dict]) -> None:
        """Commit IMPLEMENTS Decision: keyword overlap between commit message and decision."""
        dkw_map = self._decision_keywords()
        d_event = self._decision_event_map()
        for e in events:
            if e.get("kind") != "commit":
                continue
            ckw = _keywords(e.get("title", "") + " " + (e.get("body") or ""))
            if not ckw:
                continue
            for did, dkw in dkw_map.items():
                overlap = ckw & dkw
                if len(overlap) >= 2 or (overlap and len(dkw) <= 3):
                    target = d_event.get(did)
                    if target and target != e["id"]:
                        conf = min(0.95, 0.5 + 0.15 * len(overlap))
                        self._add_edge(Edge(
                            source_node=e["id"], target_node=target,
                            relationship_type=EdgeType.IMPLEMENTS.value, confidence=conf,
                            rationale=f"Commit keywords overlap decision ({len(overlap)} shared terms)",
                            provenance=[e["id"], target],
                        ))

    def _infer_discusses(self, events: list[dict]) -> None:
        """Chat message DISCUSSES Decision: message body mentions decision keywords."""
        dkw_map = self._decision_keywords()
        d_event = self._decision_event_map()
        for e in events:
            if e.get("kind") not in ("chat_message", "chat_session"):
                continue
            mkw = _keywords(e.get("title", "") + " " + (e.get("body") or ""))
            if not mkw:
                continue
            for did, dkw in dkw_map.items():
                overlap = mkw & dkw
                if len(overlap) >= 2:
                    target = d_event.get(did)
                    if target and target != e["id"]:
                        self._add_edge(Edge(
                            source_node=e["id"], target_node=target,
                            relationship_type=EdgeType.DISCUSSES.value,
                            confidence=min(0.7, 0.4 + 0.1 * len(overlap)),
                            rationale=f"Chat discusses decision (shared: {', '.join(list(overlap)[:3])})",
                            provenance=[e["id"], target],
                        ))

    def _infer_documents(self, events: list[dict]) -> None:
        """Doc DOCUMENTS Decision: doc body references decision keywords."""
        dkw_map = self._decision_keywords()
        d_event = self._decision_event_map()
        for e in events:
            if e.get("kind") not in ("doc_created", "doc_edit"):
                continue
            dkw_text = _keywords(e.get("title", "") + " " + (e.get("body") or ""))
            for did, dkw in dkw_map.items():
                overlap = dkw_text & dkw
                if len(overlap) >= 2:
                    target = d_event.get(did)
                    if target and target != e["id"]:
                        self._add_edge(Edge(
                            source_node=e["id"], target_node=target,
                            relationship_type=EdgeType.DOCUMENTS.value, confidence=0.85,
                            rationale=f"Doc references decision ({len(overlap)} shared)",
                            provenance=[e["id"], target],
                        ))

    def _infer_contains(self, events: list[dict]) -> None:
        """Release/milestone CONTAINS commits before its date."""
        releases = [e for e in events if e.get("kind") in ("release", "milestone")]
        commits = [e for e in events if e.get("kind") == "commit"]
        for rel in releases:
            rel_ts = rel.get("occurred_at") or ""
            for commit in commits:
                commit_ts = commit.get("occurred_at") or ""
                if commit_ts and rel_ts and commit_ts <= rel_ts:
                    self._add_edge(Edge(
                        source_node=rel["id"], target_node=commit["id"],
                        relationship_type=EdgeType.CONTAINS.value, confidence=0.9,
                        rationale="Commit precedes release milestone",
                        provenance=[rel["id"], commit["id"]],
                    ))

    def _infer_supersedes(self) -> None:
        """Decision SUPERSEDES Decision: status='superseded' → newer in same scope."""
        by_scope: dict[str, list[dict]] = defaultdict(list)
        for d in self._decisions:
            by_scope[d.get("scope") or "general"].append(d)
        d_event = self._decision_event_map()
        for scope, decs in by_scope.items():
            if len(decs) < 2:
                continue
            decs.sort(key=lambda d: d.get("decided_at") or "")
            for i in range(len(decs) - 1):
                old = decs[i]
                new = decs[i + 1]
                if old.get("status") in ("superseded", "deprecated", "rejected"):
                    old_e = d_event.get(old["id"])
                    new_e = d_event.get(new["id"])
                    if old_e and new_e:
                        self._add_edge(Edge(
                            source_node=new_e, target_node=old_e,
                            relationship_type=EdgeType.SUPERSEDES.value, confidence=0.95,
                            rationale=f"'{new.get('title','')}' supersedes '{old.get('title','')}' (scope={scope})",
                            provenance=[new_e, old_e],
                        ))

    def _infer_reverses(self, events: list[dict]) -> None:
        """Event REVERSES Decision: rejected/superseded decision → later event referencing it."""
        rejected = [d for d in self._decisions if d.get("status") in ("rejected", "superseded")]
        d_event = self._decision_event_map()
        for d in rejected:
            target = d_event.get(d["id"])
            if not target:
                continue
            dkw = _keywords(d.get("title", ""))
            if not dkw:
                continue
            for e in sorted(events, key=lambda x: x.get("occurred_at") or ""):
                if e["id"] == target:
                    continue
                ekw = _keywords(e.get("title", "") + " " + (e.get("body") or ""))
                if ekw & dkw and (e.get("occurred_at") or "") > (d.get("decided_at") or ""):
                    self._add_edge(Edge(
                        source_node=e["id"], target_node=target,
                        relationship_type=EdgeType.REVERSES.value, confidence=0.75,
                        rationale=f"Event references reversed decision '{d.get('title','')}'",
                        provenance=[e["id"], target],
                    ))
                    break

    def _infer_precedes(self, events: list[dict]) -> None:
        """Event PRECEDES Event: consecutive events by same actor."""
        by_actor: dict[str, list[dict]] = defaultdict(list)
        for e in events:
            if e.get("actor_id"):
                by_actor[e["actor_id"]].append(e)
        for actor, evts in by_actor.items():
            evts.sort(key=lambda e: e.get("occurred_at") or "")
            for i in range(len(evts) - 1):
                self._add_edge(Edge(
                    source_node=evts[i]["id"], target_node=evts[i + 1]["id"],
                    relationship_type=EdgeType.PRECEDES.value, confidence=0.5,
                    rationale=f"Same actor ({actor}), consecutive",
                    provenance=[evts[i]["id"], evts[i + 1]["id"]],
                ))

    # -- queries --------------------------------------------------------------

    def neighbors(self, node_id: str, relationship_type: Optional[str] = None) -> list[dict]:
        out: list[dict] = []
        for edge in self._adjacency.get(node_id, []):
            if relationship_type and edge.relationship_type != relationship_type:
                continue
            target = self.nodes.get(edge.target_node)
            if target:
                t = dict(target)
                t["_edge_type"] = edge.relationship_type
                t["_confidence"] = edge.confidence
                t["_rationale"] = edge.rationale
                out.append(t)
        return out

    def incoming(self, node_id: str, relationship_type: Optional[str] = None) -> list[dict]:
        out: list[dict] = []
        for edge in self._reverse.get(node_id, []):
            if relationship_type and edge.relationship_type != relationship_type:
                continue
            source = self.nodes.get(edge.source_node)
            if source:
                s = dict(source)
                s["_edge_type"] = edge.relationship_type
                s["_confidence"] = edge.confidence
                s["_rationale"] = edge.rationale
                out.append(s)
        return out

    def reachable(self, start_id: str, max_depth: int = 3,
                  follow_types: Optional[set[str]] = None) -> set[str]:
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(start_id, 0)]
        while queue:
            nid, depth = queue.pop(0)
            if nid in visited or depth > max_depth:
                continue
            visited.add(nid)
            for edge in self._adjacency.get(nid, []):
                if follow_types and edge.relationship_type not in follow_types:
                    continue
                if edge.target_node not in visited:
                    queue.append((edge.target_node, depth + 1))
        return visited

    def edge_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for e in self.edges:
            counts[e.relationship_type] += 1
        return dict(counts)

    def to_dict(self) -> dict:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "edge_types": self.edge_type_counts(),
            "inferred_edges": sum(1 for e in self.edges if e.confidence < 1.0),
        }

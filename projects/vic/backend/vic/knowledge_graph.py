"""Knowledge Graph — PURE INTENT REDUCER

This replaces the previous inference-based architecture.

All heuristic construction, keyword reasoning, and edge inference has been removed.
The graph is now strictly a deterministic state machine over validated intents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class KnowledgeGraph:
    """
    Pure deterministic graph state.

    Contract:
        apply_intent(intent) -> state mutation only

    No inference.
    No heuristics.
    No store coupling.
    """

    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: List[Dict[str, Any]] = field(default_factory=list)

    def __init__(self, store: Any = None):
        # store is intentionally ignored (legacy compatibility)
        self.nodes = {}
        self.edges = []

    # -----------------------------
    # Core reducer
    # -----------------------------

    def apply_intent(self, intent: Dict[str, Any]) -> None:
        op = intent.get("op")

        if op == "ADD_NODE":
            self._add_node(intent)
        elif op == "UPDATE_NODE":
            self._update_node(intent)
        elif op == "DELETE_NODE":
            self._delete_node(intent)
        elif op == "ADD_EDGE":
            self._add_edge(intent)
        else:
            # UNRESOLVED or unknown ops are ignored deterministically
            return

    # -----------------------------
    # Node operations
    # -----------------------------

    def _add_node(self, intent: Dict[str, Any]) -> None:
        node = intent.get("node", {})
        node_id = node.get("entity_id")
        if not node_id:
            return
        self.nodes[node_id] = node

    def _update_node(self, intent: Dict[str, Any]) -> None:
        node = intent.get("node", {})
        node_id = node.get("entity_id")
        if not node_id or node_id not in self.nodes:
            return
        self.nodes[node_id].update(node)

    def _delete_node(self, intent: Dict[str, Any]) -> None:
        node_id = intent.get("node", {}).get("entity_id")
        if not node_id:
            return

        if node_id in self.nodes:
            del self.nodes[node_id]

        # strict cleanup of edges
        self.edges = [
            e for e in self.edges
            if e.get("from") != node_id and e.get("to") != node_id
        ]

    # -----------------------------
    # Edge operations
    # -----------------------------

    def _add_edge(self, intent: Dict[str, Any]) -> None:
        src = intent.get("from")
        dst = intent.get("to")
        rel = intent.get("relation")

        if not src or not dst or not rel:
            return

        self.edges.append({
            "from": src,
            "to": dst,
            "relation": rel,
        })

    # -----------------------------
    # Read-only helpers (no inference)
    # -----------------------------

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.nodes.get(node_id)

    def get_edges(self) -> List[Dict[str, Any]]:
        return list(self.edges)

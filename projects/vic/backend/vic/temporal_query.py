from typing import List, Dict, Any, Optional


class TemporalQueryEngine:
    """
    Deterministic query layer over NarrativeEngine.

    This does NOT store new state.
    It computes over:
        - arcs (temporal segments)
        - entities
        - provenance traces
    """

    def __init__(self, narrative_engine):
        self.narrative = narrative_engine

    def find_first_occurrence(self, entity: str):
        for arc in self.narrative.list_arcs():
            if entity in arc.entities:
                return arc
        return None

    def trace_entity_lifecycle(self, entity: str) -> List[Dict[str, Any]]:
        trace = []
        for arc in self.narrative.list_arcs():
            if entity in arc.entities:
                trace.append({
                    "arc_id": arc.arc_id,
                    "title": arc.title,
                    "story": arc.story,
                    "provenance": arc.provenance
                })
        return trace

    def reconstruct_at_arc(self, arc_id: str) -> Dict[str, Any]:
        """Reconstruct the graph state as of a given arc.

        Replays all provenance entries from arcs up to and including arc_id,
        collecting ADD_NODE and ADD_EDGE operations into a snapshot.
        """
        arcs = self.narrative.list_arcs()

        snapshot_nodes: dict[str, dict] = {}
        snapshot_edges: list[dict] = []

        for arc in arcs:
            if arc.arc_id > arc_id:
                break

            for p in arc.provenance:
                if not isinstance(p, dict):
                    continue
                op = p.get("op")
                if op == "ADD_NODE":
                    node = p.get("node", {})
                    node_id = node.get("entity_id") or node.get("id")
                    if node_id:
                        snapshot_nodes[node_id] = node
                elif op == "ADD_EDGE":
                    snapshot_edges.append({
                        "from": p.get("from"),
                        "to": p.get("to"),
                        "relation": p.get("relation"),
                        "provenance": p.get("provenance", {}),
                    })

        return {
            "arc_id": arc_id,
            "nodes": snapshot_nodes,
            "edges": snapshot_edges,
        }

    def causal_chain(self, entity: str) -> List[str]:
        chain = []
        for arc in self.narrative.list_arcs():
            if entity in arc.entities:
                chain.append(arc.arc_id)
        return chain

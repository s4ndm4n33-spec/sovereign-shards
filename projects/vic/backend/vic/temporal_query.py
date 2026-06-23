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
        arcs = self.narrative.list_arcs()

        snapshot_nodes = {}
        snapshot_edges = []

        for arc in arcs:
            if arc.arc_id > arc_id:
                break

            for p in arc.provenance:
                if "ADD_NODE" in p:
                    continue

        return {
            "arc_id": arc_id,
            "nodes": snapshot_nodes,
            "edges": snapshot_edges
        }

    def causal_chain(self, entity: str) -> List[str]:
        chain = []
        for arc in self.narrative.list_arcs():
            if entity in arc.entities:
                chain.append(arc.arc_id)
        return chain

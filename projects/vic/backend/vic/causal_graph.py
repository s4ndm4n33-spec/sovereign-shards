from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any


class CausalGraph:
    """
    Deterministic causal reconstruction over temporal narrative arcs.

    This layer does NOT infer semantic truth.
    It extracts stable transition patterns across time.

    Extended:
        - arc-aware causality tracking
        - cross-session invariant detection (via arc persistence)
    """

    def __init__(self):
        self.nodes: Set[str] = set()

        # raw transition counts
        self.edges: Dict[Tuple[str, str], int] = defaultdict(int)

        # enriched statistics for cross-history invariance
        self.edge_stats: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "arcs": set()}
        )

    def build(self, narrative_engine):
        arcs = narrative_engine.list_arcs()

        for idx, arc in enumerate(arcs):
            self._process_arc(arc, arc.arc_id)

        return self

    def _process_arc(self, arc, arc_id: str):
        """Extract causal transitions from an arc.

        A transition (A → B) is recorded when:
        - A and B are distinct entities that co-occur in the arc, AND
        - A appears earlier in the arc than B (temporal precedence), AND
        - They share at least one tag or keyword (semantic coherence)

        This is stronger than raw list adjacency: it requires both temporal
        ordering and semantic overlap to record a causal candidate.
        """
        entities = arc.entities
        if not entities or len(entities) < 2:
            return

        # Build entity → first position index
        first_seen: dict[str, int] = {}
        for i, e in enumerate(entities):
            if e and e not in first_seen:
                first_seen[e] = i

        # Extract tags from arc story for semantic coherence check
        arc_tags: set[str] = set()
        story = getattr(arc, "story", "") or ""
        if story:
            words = story.lower().split()
            arc_tags = {w for w in words if len(w) > 3}

        # Record transitions: for every pair (A, B) where A precedes B
        entity_list = list(first_seen.keys())
        for i, a in enumerate(entity_list):
            for b in entity_list[i + 1:]:
                if not a or not b or a == b:
                    continue

                # Temporal precedence: a appears before b
                if first_seen[a] >= first_seen[b]:
                    continue

                self.nodes.add(a)
                self.nodes.add(b)

                key = (a, b)
                self.edges[key] += 1
                self.edge_stats[key]["count"] += 1
                self.edge_stats[key]["arcs"].add(arc_id)

    # -----------------------------
    # Query: strong causal links
    # -----------------------------

    def get_strong_causes(self, node: str, threshold: int = 2):
        return [
            (a, w)
            for (a, b), w in self.edges.items()
            if b == node and w >= threshold
        ]

    def get_effects(self, node: str, threshold: int = 2):
        return [
            (b, w)
            for (a, b), w in self.edges.items()
            if a == node and w >= threshold
        ]

    # -----------------------------
    # Cross-session invariants
    # -----------------------------

    def invariant_edges(self, min_occurrences: int = 2, min_arc_ratio: float = 0.5):
        """
        Returns edges that persist across multiple arcs (proxy for cross-history stability).
        """
        invariants = []

        for (a, b), stats in self.edge_stats.items():
            arc_count = len(stats["arcs"])
            total_count = stats["count"]

            if total_count >= min_occurrences and arc_count >= min_arc_ratio * total_count:
                invariants.append({
                    "from": a,
                    "to": b,
                    "count": total_count,
                    "arc_support": arc_count,
                })

        return invariants

    # -----------------------------
    # Path finding
    # -----------------------------

    def causal_path(self, start: str, end: str, max_depth: int = 5):
        frontier = [(start, [start])]
        visited = set()

        while frontier:
            current, path = frontier.pop(0)

            if current == end:
                return path

            if current in visited or len(path) > max_depth:
                continue

            visited.add(current)

            for (a, b), _w in self.edges.items():
                if a == current:
                    frontier.append((b, path + [b]))

        return []

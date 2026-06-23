from collections import defaultdict
from typing import Dict, List, Set, Tuple


class CausalGraph:
    """
    Deterministic causal reconstruction over temporal narrative arcs.

    This layer does NOT infer semantic truth.
    It extracts stable transition patterns across time.
    """

    def __init__(self):
        self.nodes: Set[str] = set()
        self.edges: Dict[Tuple[str, str], int] = defaultdict(int)

    def build(self, narrative_engine):
        arcs = narrative_engine.list_arcs()

        for arc in arcs:
            self._process_arc(arc)

        return self

    def _process_arc(self, arc):
        entities = arc.entities

        for i in range(len(entities) - 1):
            a = entities[i]
            b = entities[i + 1]

            if not a or not b:
                continue

            self.nodes.add(a)
            self.nodes.add(b)

            self.edges[(a, b)] += 1

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

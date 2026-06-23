from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class NarrativeBlock:
    arc_id: str
    time_range: str
    title: str
    story: str
    entities: List[str]
    provenance: List[str]


class NarrativeEngine:
    """
    Deterministic narrative reconstruction + temporal DSL layer.

    Core idea:
        - IR defines change
        - Graph stores state
        - Narrative layer projects *queryable history objects*

    This is no longer just rendering.
    It is a temporal index over system evolution.
    """

    def __init__(self):
        self._arcs: Dict[str, NarrativeBlock] = {}
        self._arc_order: List[str] = []
        self._counter: int = 0

    # -----------------------------
    # Public API
    # -----------------------------

    def build(self, graph, ir: Dict[str, Any], sessions: List[Dict]) -> List[NarrativeBlock]:
        intents = ir.get("intents", []) if ir else []

        timeline = self._build_timeline(intents, sessions)
        arcs = self._build_arcs(graph, timeline)

        rendered = []
        for arc in arcs:
            block = self._render_arc(arc)
            self._register(block)
            rendered.append(block)

        return rendered

    def get_arc(self, arc_id: str) -> Optional[NarrativeBlock]:
        return self._arcs.get(arc_id)

    def list_arcs(self) -> List[NarrativeBlock]:
        return [self._arcs[i] for i in self._arc_order if i in self._arcs]

    def query_by_entity(self, entity: str) -> List[NarrativeBlock]:
        return [a for a in self.list_arcs() if entity in a.entities]

    # -----------------------------
    # Timeline construction
    # -----------------------------

    def _build_timeline(self, intents, sessions):
        events = []

        for s in sessions:
            events.append({
                "time": s.get("date"),
                "type": "session",
                "data": s
            })

        for i in intents:
            events.append({
                "time": None,
                "type": "intent",
                "data": i
            })

        return events

    # -----------------------------
    # Arc segmentation (deterministic v1)
    # -----------------------------

    def _build_arcs(self, graph, timeline):
        arcs = []
        current = []

        for event in timeline:
            current.append(event)

            if len(current) >= 5:
                arcs.append(current)
                current = []

        if current:
            arcs.append(current)

        return arcs

    # -----------------------------
    # Rendering (projection layer only)
    # -----------------------------

    def _render_arc(self, arc) -> NarrativeBlock:
        entities = set()
        provenance = []

        for e in arc:
            data = e["data"]

            if e["type"] == "session":
                entities.add(data.get("title", ""))

            elif e["type"] == "intent":
                if isinstance(data, dict):
                    node = data.get("node") or {}
                    if isinstance(node, dict):
                        entities.add(node.get("entity_id", ""))

                    if "from" in data:
                        entities.add(data.get("from", ""))
                    if "to" in data:
                        entities.add(data.get("to", ""))

                provenance.append(str(data))

        arc_id = self._next_id()

        return NarrativeBlock(
            arc_id=arc_id,
            time_range="unbounded",
            title=self._generate_title(arc),
            story=self._render_story(arc),
            entities=[e for e in entities if e],
            provenance=provenance
        )

    # -----------------------------
    # Registration / indexing
    # -----------------------------

    def _register(self, block: NarrativeBlock) -> None:
        self._arcs[block.arc_id] = block
        self._arc_order.append(block.arc_id)

    def _next_id(self) -> str:
        self._counter += 1
        return f"arc_{self._counter}"

    # -----------------------------
    # Deterministic rendering rules
    # -----------------------------

    def _generate_title(self, arc) -> str:
        first = arc[0]["type"] if arc else "unknown"
        last = arc[-1]["type"] if arc else "unknown"
        return f"{first} → {last} transformation window"

    def _render_story(self, arc) -> str:
        lines = []

        for e in arc:
            if e["type"] == "session":
                s = e["data"]
                lines.append(
                    f"During session '{s.get('title','unknown')}', the system processed structured state."
                )

            elif e["type"] == "intent":
                i = e["data"] or {}

                if i.get("op") == "ADD_NODE":
                    n = i.get("node", {})
                    lines.append(
                        f"A structural node '{n.get('entity_id')}' was introduced into the graph."
                    )

                elif i.get("op") == "ADD_EDGE":
                    lines.append(
                        f"A deterministic relationship was established between {i.get('from')} and {i.get('to')}."
                    )

        return " ".join(lines)

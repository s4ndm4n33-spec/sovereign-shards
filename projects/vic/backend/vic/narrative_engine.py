from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class NarrativeBlock:
    time_range: str
    title: str
    story: str
    entities: List[str]
    provenance: List[str]


class NarrativeEngine:
    """
    Deterministic narrative reconstruction over:
    - IR (intent stream)
    - KnowledgeGraph state
    - session timeline

    No inference. No hallucination.
    Only structured temporal rendering.
    """

    def build(self, graph, ir: Dict[str, Any], sessions: List[Dict]) -> List[NarrativeBlock]:
        intents = ir.get("intents", []) if ir else []

        timeline = self._build_timeline(intents, sessions)
        arcs = self._build_arcs(graph, timeline)

        return [self._render_arc(arc) for arc in arcs]

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

    def _render_arc(self, arc) -> NarrativeBlock:
        entities = set()
        provenance = []

        for e in arc:
            data = e["data"]

            if e["type"] == "session":
                entities.add(data.get("title", ""))

            elif e["type"] == "intent":
                if isinstance(data, dict):
                    if "node" in data:
                        node = data["node"] or {}
                        entities.add(node.get("entity_id", ""))

                    if "from" in data:
                        entities.add(data.get("from", ""))
                    if "to" in data:
                        entities.add(data.get("to", ""))

                provenance.append(str(data))

        return NarrativeBlock(
            time_range="unbounded",
            title=self._generate_title(arc),
            story=self._render_story(arc),
            entities=[e for e in entities if e],
            provenance=provenance
        )

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
                        f"A deterministic relationship was established between {i.get('from')} and {i.get('to')}.")

        return " ".join(lines)

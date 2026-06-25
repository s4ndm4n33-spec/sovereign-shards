"""Deterministic agent for V.I.C. pipeline.

Converts parsed session data into a graph intent IR (intermediate representation).
Output is strictly:
    { "intents": [ ... ] }

No inference. Only deterministic schema-based translation.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List


_DECISION_RE = re.compile(
    r"\b(we decided|let'?s use|chose to|will adopt|decided to use|"
    r"going with|settled on)\b",
    re.IGNORECASE,
)
_BUG_RE = re.compile(r"\b(bug|crash|error|broken|fails|exception)\b", re.IGNORECASE)
_FIX_RE = re.compile(r"\b(fixed|resolved|patched|corrected)\b", re.IGNORECASE)
_ARCH_RE = re.compile(
    r"\b(architecture|refactor|module|interface|pattern|component)\b",
    re.IGNORECASE,
)


def _entity_id(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", "_", normalized)


def _hash(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


class DeterministicAgent:
    """Deterministic translation from session dicts to graph intents."""

    def process(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        text = raw.get("text", "")
        try:
            sessions = json.loads(text) if isinstance(text, str) else text
        except (json.JSONDecodeError, TypeError):
            sessions = []

        if not isinstance(sessions, list):
            sessions = []

        intents: List[Dict[str, Any]] = []

        for session in sessions:
            if not isinstance(session, dict):
                continue

            session_idx = session.get("session", 0)
            provider = session.get("provider", "unknown")
            title = session.get("title", "")
            date = session.get("date", "")

            provenance = {
                "session": session_idx,
                "provider": provider,
                "date": date,
                "source": "deterministic_agent",
            }

            # Session node
            if title:
                node_id = _entity_id(f"session_{session_idx}_{title}")
                intents.append({
                    "op": "ADD_NODE",
                    "node": {
                        "entity_id": node_id,
                        "type": "EVENT",
                        "surface_forms": [title],
                        "metadata": {"kind": "session", "provider": provider, "date": date},
                    },
                    "provenance": provenance,
                })

            # Decision nodes
            for decision in session.get("decisions", []):
                if not isinstance(decision, str) or not decision.strip():
                    continue
                dec_id = _entity_id(f"decision_{decision}")
                intents.append({
                    "op": "ADD_NODE",
                    "node": {
                        "entity_id": dec_id,
                        "type": "EVENT",
                        "surface_forms": [decision],
                        "metadata": {"kind": "decision"},
                    },
                    "provenance": provenance,
                })
                if title:
                    intents.append({
                        "op": "ADD_EDGE",
                        "from": _entity_id(f"session_{session_idx}_{title}"),
                        "to": dec_id,
                        "relation": "CONTAINS",
                        "provenance": provenance,
                    })

            # Bug/fix/architecture nodes
            for kind, items in (
                ("bug", session.get("bugs", [])),
                ("fix", session.get("fixes", [])),
                ("architecture", session.get("architecture", [])),
            ):
                for item in items:
                    if not isinstance(item, str) or not item.strip():
                        continue
                    item_id = _entity_id(f"{kind}_{item}")
                    intents.append({
                        "op": "ADD_NODE",
                        "node": {
                            "entity_id": item_id,
                            "type": "EVENT",
                            "surface_forms": [item],
                            "metadata": {"kind": kind},
                        },
                        "provenance": provenance,
                    })

        return {"intents": intents}

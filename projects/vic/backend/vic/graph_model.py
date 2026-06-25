"""Typed relationship edges and provenance claims for the V.I.C. knowledge graph.

Phase 1 — Typed Relationships:
  Each edge has: id, source_node, target_node, relationship_type,
  confidence, provenance (evidence event ids), rationale, created_at.

Phase 3 — Provenance:
  Every derived fact is a Claim with an evidence chain and confidence.
  The system can answer "Why does V.I.C. believe this?" by returning
  the supporting evidence.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class EdgeType(str, Enum):
    IMPLEMENTS = "implements"
    SUPERSEDES = "supersedes"
    MOTIVATED = "motivated"
    INSPIRED = "inspired"
    CONTAINS = "contains"
    DOCUMENTS = "documents"
    REFERENCES = "references"
    DISCUSSES = "discusses"
    DEPENDS_ON = "depends_on"
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    REVERSES = "reverses"
    REFINES = "refines"
    RESOLVES = "resolves"
    REPLACES = "replaces"


@dataclass
class Edge:
    """A typed relationship between two nodes in the knowledge graph."""
    source_node: str
    target_node: str
    relationship_type: str  # EdgeType value
    confidence: float = 1.0
    rationale: str = ""
    provenance: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def id(self) -> str:
        raw = f"{self.source_node}|{self.target_node}|{self.relationship_type}".encode()
        return hashlib.sha1(raw).hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Claim:
    """A derived fact with an evidence chain and confidence score.

    Allows V.I.C. to explain *why* it believes something, not just *what*.
    """
    subject: str
    predicate: str
    obj: str
    evidence: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    inference_rule: str = ""
    derived_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

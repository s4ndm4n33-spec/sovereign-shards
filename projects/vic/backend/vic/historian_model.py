"""Core data model for V.I.C. as an automated software historian.

Entities:
  - Person:       a human or bot that authored commits / messages / docs
  - Repository:   a git repo (or logical project) that events belong to
  - Session:      a chat conversation (already existed; now a Source subtype)
  - Decision:     an explicit decision with rationale and scope
  - Artifact:     a produced artifact (commit, PR, doc, diagram, release)
  - Milestone:    a named point in time (release, freeze, demo, EOL)
  - Event:        the universal timeline atom — any timestamped fact
  - Narrative:    a generated human-readable story spanning linked events

Design principles:
  - Every timestamped fact is an Event. Sessions, commits, PRs, decisions,
    releases, and doc edits are all modelled as Events with a `kind` and
    a pointer to a typed detail row. This lets the timeline engine and
    semantic search operate uniformly over the entire history.
  - Sovereignty: all data lives in a local embedded SQLite store on the
    user's machine. No cloud, no remote calls.
  - Provenance: every Event carries a `source_kind` and `source_ref`
    so narratives can cite where each fact came from.
"""

from json import JSONEncoder
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums (serialised as strings in SQLite)
# ---------------------------------------------------------------------------

class EventKind(str, Enum):
    CHAT_MESSAGE = "chat_message"
    CHAT_SESSION = "chat_session"
    COMMIT = "commit"
    PR_OPENED = "pr_opened"
    PR_MERGED = "pr_merged"
    PR_CLOSED = "pr_closed"
    ISSUE_OPENED = "issue_opened"
    ISSUE_CLOSED = "issue_closed"
    ISSUE_COMMENT = "issue_comment"
    DECISION = "decision"
    DOC_EDIT = "doc_edit"
    DOC_CREATED = "doc_created"
    RELEASE = "release"
    MILESTONE = "milestone"
    DIAGRAM = "diagram"
    REVIEW = "review"


class SourceKind(str, Enum):
    CHATGPT = "chatgpt"
    CLAUDE = "claude"
    GEMINI = "gemini"
    GIT = "git"
    MARKDOWN = "markdown"
    NOTES = "notes"
    GITHUB = "github"
    MANUAL = "manual"
    CRAWLED = "crawled"


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class ArtifactKind(str, Enum):
    COMMIT = "commit"
    PR = "pr"
    ISSUE = "issue"
    DOC = "doc"
    DIAGRAM = "diagram"
    RELEASE = "release"
    CONFIG = "config"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _from_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        v = s
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        d = datetime.fromisoformat(v)
        return d
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------

@dataclass
class Person:
    id: str  # stable id (email-hash / username / 'unknown')
    name: str = ""
    email: str = ""
    username: str = ""
    role: str = ""  # "author" / "reviewer" / "maintainer" — informal
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    aliases: list[str] = field(default_factory=list)


@dataclass
class Repository:
    id: str  # repo key (name or url-hash)
    name: str = ""
    url: str = ""
    default_branch: str = "main"
    description: str = ""
    language: str = ""
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


@dataclass
class Decision:
    id: str
    repository_id: str
    title: str
    rationale: str = ""
    status: str = DecisionStatus.ACCEPTED.value
    scope: str = ""  # "backend" / "frontend" / "runtime" / freeform
    decided_at: Optional[str] = None
    decided_by: str = ""  # person id
    superseded_by: Optional[str] = None  # decision id
    tags: list[str] = field(default_factory=list)


@dataclass
class Artifact:
    id: str
    repository_id: str
    kind: str  # ArtifactKind value
    ref: str = ""  # sha / pr number / doc path / release tag
    title: str = ""
    path: str = ""
    created_at: Optional[str] = None
    author_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Milestone:
    id: str
    repository_id: str
    name: str
    description: str = ""
    achieved_at: Optional[str] = None
    kind: str = "release"  # release | freeze | demo | eol | custom
    tags: list[str] = field(default_factory=list)


@dataclass
class Session:
    """A chat conversation. Kept compatible with the original models.Conversation
    shape but normalised to the historian model."""

    id: str
    repository_id: str = ""
    provider: str = ""
    source_ref: str = ""
    title: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    project: str = ""
    message_count: int = 0
    summary: str = ""


@dataclass
class Event:
    """The universal timeline atom.

    Every timestamped fact — a chat message, a commit, a PR, a decision,
    a doc edit, a release — is stored as an Event with a `kind` and a
    typed detail pointer (`detail_id` → row in a kind-specific table).
    """
    id: str
    repository_id: str = ""
    kind: str = EventKind.CHAT_MESSAGE.value
    source_kind: str = SourceKind.MANUAL.value  # provenance
    source_ref: str = ""  # e.g. share URL, git ref, file path
    occurred_at: Optional[str] = None  # ISO timestamp
    ended_at: Optional[str] = None  # for ranged events (PRs, sessions)
    actor_id: str = ""  # person id
    title: str = ""
    body: str = ""  # canonical text for semantic indexing
    detail_id: str = ""  # → id in the kind-specific detail table
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)  # ids of related events
    importance: float = 0.5  # 0..1, used to surface significant events
    created_at: str = field(default_factory=_now_iso)


@dataclass
class Narrative:
    id: str
    repository_id: str = ""
    title: str = ""
    body: str = ""
    kind: str = "executive_summary"  # executive_summary | arch_evolution | dep_evolution | state_of_project | custom
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    query: str = ""
    event_ids: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    generated_at: str = field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

class ModelEncoder(JSONEncoder):
    def default(self, o):  # noqa: D401
        if isinstance(o, datetime):
            return _to_iso(o)
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        return super().default(o)


def to_dict(obj) -> dict:
    return asdict(obj) if hasattr(obj, "__dataclass_fields__") else dict(obj)

"""Ingestion pipeline: normalize disparate sources into Events in the store.

Sources:
  - Git commits (parse `git log` output from a local repo path)
  - Markdown documents (front-matter + headings + body)
  - Structured notes (JSON / TOML-ish: decisions, milestones, meeting notes)
  - Chat conversations (reuse existing parsers; emit chat_message events)
  - Crawled shared chats (reuse crawler; emit chat_message events)
  - Pull requests / issues (JSON or markdown export; GitHub shape supported)

Each ingest* function mutates the Store and returns a summary dict.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .historian_model import (
    Artifact,
    ArtifactKind,
    Decision,
    DecisionStatus,
    Event,
    EventKind,
    Milestone,
    Narrative,
    Person,
    Repository,
    Session,
    SourceKind,
    to_dict,
)
from .models import Conversation, Message
from .store import Store

log = logging.getLogger("vic.ingest")


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        v = s
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        return datetime.fromisoformat(v)
    except (ValueError, TypeError):
        return None


def _ensure_repo(store: Store, repo_id: str, name: str = "", url: str = "", **extra) -> str:
    repo = Repository(
        id=repo_id,
        name=name or repo_id,
        url=url,
        default_branch=extra.get("default_branch", "main"),
        description=extra.get("description", ""),
        language=extra.get("language", ""),
        first_seen=_iso(datetime.now(timezone.utc)),
        last_seen=_iso(datetime.now(timezone.utc)),
    )
    store.upsert_repository(repo)
    return repo.id


# ---------------------------------------------------------------------------
# Git commits
# ---------------------------------------------------------------------------

_GIT_LOG_FORMAT = "%x1e%H%x1f%an%x1f%ae%x1f%ad%x1f%s%x1f%b%x1f%cn%x1f%ce%x1f%cd%x1f%P"
_DATE_FMT = "%Y-%m-%dT%H:%M:%S%z"


def ingest_git(store: Store, repo_path: str | Path, repo_id: Optional[str] = None, limit: int = 5000) -> dict:
    """Ingest commits from a local git repository.

    Uses `git log` with a custom separator format. Each commit becomes an
    Event (kind=commit) plus an Artifact (kind=commit). Authors are
    upserted as Persons. Returns a summary dict.
    """
    repo_path = Path(repo_path)
    if not (repo_path / ".git").exists() and not repo_path.is_dir():
        raise FileNotFoundError(f"Not a git repository: {repo_path}")

    # Derive repo identity
    try:
        url = subprocess.check_output(
            ["git", "-C", str(repo_path), "config", "--get", "remote.origin.url"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        url = ""
    name = repo_path.name
    repo_id = repo_id or _stable_id("git", name, url) or _stable_id("git", str(repo_path))
    _ensure_repo(store, repo_id, name=name, url=url)

    try:
        raw = subprocess.check_output(
            ["git", "-C", str(repo_path), "log", f"--pretty=format:{_GIT_LOG_FORMAT}", f"--date=iso-strict", f"-n{limit}"],
            stderr=subprocess.DEVNULL, text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        log.warning("git log failed for %s: %s", repo_path, exc)
        return {"repository_id": repo_id, "commits": 0, "error": str(exc)}

    if not raw.strip():
        return {"repository_id": repo_id, "commits": 0}

    # Parse custom format
    records = raw.split("\x1e")
    count = 0
    for rec in records:
        rec = rec.strip("\n")
        if not rec:
            continue
        parts = rec.split("\x1f")
        if len(parts) < 10:
            continue
        sha, an, ae, ad, subj, body, cn, ce, cd, parents = parts[:10]
        try:
            occurred = _parse_git_date(ad) or _parse_git_date(cd)
        except (ValueError, TypeError):
            occurred = None

        author_id = _stable_id("person", (ae or ce or an or cn or "unknown").lower())
        store.upsert_person(Person(
            id=author_id, name=an or cn, email=ae or ce, username=(ae or ce or "").split("@")[0],
            role="author", first_seen=_iso(occurred), last_seen=_iso(occurred),
        ))

        artifact = Artifact(
            id=_stable_id("artifact", "commit", sha),
            repository_id=repo_id, kind=ArtifactKind.COMMIT.value, ref=sha,
            title=subj.strip(), path="", created_at=_iso(occurred), author_id=author_id,
            metadata={"body": body.strip(), "committer": cn, "committer_email": ce, "parents": parents.split()},
        )
        store.upsert_artifact(artifact)

        importance = _commit_importance(subj, body)
        event = Event(
            id=_stable_id("event", "commit", sha),
            repository_id=repo_id,
            kind=EventKind.COMMIT.value,
            source_kind=SourceKind.GIT.value,
            source_ref=f"{name}@{sha[:8]}",
            occurred_at=_iso(occurred),
            actor_id=author_id,
            title=subj.strip(),
            body=body.strip(),
            detail_id=artifact.id,
            tags=_commit_tags(subj, body),
            importance=importance,
        )
        store.upsert_event(event)
        count += 1

    return {"repository_id": repo_id, "commits": count}


def _parse_git_date(s: str) -> Optional[datetime]:
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace(" ", "T")) if " " in s else datetime.fromisoformat(s)
    except ValueError:
        return None


_RE_MAJOR = re.compile(r"^(feat|fix|refactor|chore|docs|style|test|perf|build|ci|revert|breaking)\b", re.IGNORECASE)
_RE_BREAKING = re.compile(r"BREAKING CHANGE|\!:", re.IGNORECASE)


def _commit_importance(subject: str, body: str) -> float:
    if _RE_BREAKING.search(subject) or _RE_BREAKING.search(body):
        return 0.95
    if _RE_MAJOR.match(subject):
        m = _RE_MAJOR.match(subject).group(1).lower()
        if m in ("feat", "refactor", "breaking"):
            return 0.8
        if m in ("fix", "perf"):
            return 0.6
        return 0.5
    if "merge" in subject.lower():
        return 0.7
    return 0.35


def _commit_tags(subject: str, body: str) -> list[str]:
    tags: list[str] = []
    m = _RE_MAJOR.match(subject)
    if m:
        tags.append(m.group(1).lower())
    if _RE_BREAKING.search(subject) or _RE_BREAKING.search(body):
        tags.append("breaking")
    if "merge" in subject.lower():
        tags.append("merge")
    # Scopes like feat(parser): → capture parser
    m = re.match(r"^[a-z]+\(([^)]+)\)", subject)
    if m:
        tags.append(m.group(1).lower())
    return tags


# ---------------------------------------------------------------------------
# Markdown documents
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def ingest_markdown(store: Store, path: str | Path, repo_id: str, source_kind: str = SourceKind.MARKDOWN.value) -> dict:
    """Ingest a markdown document.
    Front-matter (YAML-ish) is parsed loosely; title from first H1 or filename.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8", errors="ignore")

    # Front matter
    fm: dict[str, Any] = {}
    body = text
    m = _FM_RE.match(text)
    if m:
        fm_raw, body = m.group(1), m.group(2)
        fm = _parse_loose_yaml(fm_raw)

    title = fm.get("title") or _first_h1(body) or path.stem
    actor_id = _stable_id("person", str(fm.get("author") or "unknown").lower())
    if fm.get("author"):
        store.upsert_person(Person(id=actor_id, name=str(fm.get("author")), role="author"))
    occurred_raw = fm.get("date") or fm.get("created") or fm.get("updated")
    occurred = _parse_iso(str(occurred_raw)) if occurred_raw else datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)

    artifact = Artifact(
        id=_stable_id("artifact", "doc", str(path), str(occurred)),
        repository_id=repo_id, kind=ArtifactKind.DOC.value, ref=str(path),
        title=title, path=str(path), created_at=_iso(occurred),
        author_id=actor_id, metadata={"front_matter": fm, "headings": _extract_headings(body)},
    )
    store.upsert_artifact(artifact)

    event = Event(
        id=_stable_id("event", "doc", str(path), str(occurred)),
        repository_id=repo_id, kind=EventKind.DOC_CREATED.value,
        source_kind=source_kind, source_ref=str(path),
        occurred_at=_iso(occurred), actor_id=actor_id,
        title=title, body=body.strip()[:4000], detail_id=artifact.id,
        tags=_md_tags(fm, body), importance=0.55,
    )
    store.upsert_event(event)

    # If the document looks like a decision record, also emit a Decision
    if _looks_like_adr(body, title):
        decision = Decision(
            id=_stable_id("decision", "doc", str(path)),
            repository_id=repo_id,
            title=title,
            rationale=_extract_section(body, "Context", "Decision") or body[:400],
            status=DecisionStatus.ACCEPTED.value,
            scope=str(fm.get("scope") or ""),
            decided_at=_iso(occurred),
            decided_by=actor_id,
            tags=_md_tags(fm, body),
        )
        store.upsert_decision(decision)

    return {"repository_id": repo_id, "doc": str(path), "title": title, "decision": _looks_like_adr(body, title)}


def _parse_loose_yaml(raw: str) -> dict[str, Any]:
    """Loose YAML parser for simple `key: value` front-matter."""
    out: dict[str, Any] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if v.lower() in ("true", "false"):
            out[k] = v.lower() == "true"
        elif v.isdigit():
            out[k] = int(v)
        else:
            out[k] = v
    return out


def _first_h1(body: str) -> Optional[str]:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _extract_headings(body: str) -> list[str]:
    return [line.strip().lstrip("# ").strip() for line in body.splitlines() if line.strip().startswith("#")]


def _md_tags(fm: dict[str, Any], body: str) -> list[str]:
    tags: list[str] = []
    if fm.get("tags"):
        if isinstance(fm["tags"], str):
            tags.extend(t.strip() for t in fm["tags"].split(","))
        elif isinstance(fm["tags"], list):
            tags.extend(str(t) for t in fm["tags"])
    if fm.get("category"):
        tags.append(str(fm["category"]).lower())
    return tags


def _looks_like_adr(body: str, title: str) -> bool:
    low = (title + " " + body[:1000]).lower()
    return any(k in low for k in ("adr", "decision record", "context and decision", "status: accepted", "decision:"))


def _extract_section(body: str, *headers: str) -> Optional[str]:
    lines = body.splitlines()
    for i, line in enumerate(lines):
        low = line.strip().lower().lstrip("# ").strip()
        if any(h.lower() in low for h in headers):
            # capture until next heading or two blank lines
            out: list[str] = []
            for nxt in lines[i + 1 :]:
                if nxt.strip().startswith("#"):
                    break
                out.append(nxt)
                if len(out) > 1 and not nxt.strip() and not out[-2].strip():
                    break
            return "\n".join(out).strip()
    return None


# ---------------------------------------------------------------------------
# Structured notes (JSON)
# ---------------------------------------------------------------------------

def ingest_structured_notes(store: Store, path: str | Path, repo_id: str) -> dict:
    """Ingest a JSON file containing decisions, milestones, or notes.

    Expected shapes (any subset present is handled):
      {"decisions": [...], "milestones": [...], "notes": [...]}
      {"type": "decision" | "milestone", ...}
      [{"date": ..., "event": "...", "summary": "..."}]  # generic timeline notes
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))

    # Unwrap common containers
    if isinstance(data, dict):
        items: list = []
        for key in ("decisions", "milestones", "notes", "items", "events"):
            v = data.get(key)
            if isinstance(v, list):
                items.extend(v)
            elif isinstance(v, dict):
                items.append(v)
        if not items:
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        return {"repository_id": repo_id, "notes": 0}

    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = (item.get("type") or "").lower()
        occurred = _parse_iso(str(item.get("date") or item.get("decided_at") or item.get("achieved_at")))

        if kind == "decision" or "decision" in item or item.get("rationale"):
            d = Decision(
                id=item.get("id") or _stable_id("decision", "note", str(path), str(occurred or "")),
                repository_id=repo_id,
                title=item.get("title") or item.get("decision") or item.get("summary", ""),
                rationale=item.get("rationale") or item.get("context") or "",
                status=item.get("status", DecisionStatus.ACCEPTED.value),
                scope=item.get("scope", ""),
                decided_at=_iso(occurred),
                decided_by=_stable_id("person", str(item.get("decided_by") or "unknown").lower()),
                tags=item.get("tags", []),
            )
            store.upsert_decision(d)
            store.upsert_event(Event(
                id=_stable_id("event", "decision", d.id),
                repository_id=repo_id, kind=EventKind.DECISION.value,
                source_kind=SourceKind.NOTES.value, source_ref=str(path),
                occurred_at=_iso(occurred), title=d.title, body=d.rationale,
                detail_id=d.id, tags=d.tags, importance=0.85,
            ))
            count += 1

        elif kind == "milestone" or item.get("achieved_at"):
            m = Milestone(
                id=item.get("id") or _stable_id("milestone", "note", str(path), str(occurred or "")),
                repository_id=repo_id,
                name=item.get("name") or item.get("title", ""),
                description=item.get("description") or item.get("summary", ""),
                achieved_at=_iso(occurred),
                kind=item.get("kind", "release"),
                tags=item.get("tags", []),
            )
            store.upsert_milestone(m)
            store.upsert_event(Event(
                id=_stable_id("event", "milestone", m.id),
                repository_id=repo_id, kind=EventKind.MILESTONE.value,
                source_kind=SourceKind.NOTES.value, source_ref=str(path),
                occurred_at=_iso(occurred), title=m.name, body=m.description,
                detail_id=m.id, tags=m.tags, importance=0.9,
            ))
            count += 1

        else:
            # Generic note → an event
            title = item.get("title") or item.get("event") or item.get("summary", "")
            body = item.get("body") or item.get("note") or item.get("details", "")
            evt = Event(
                id=_stable_id("event", "note", str(path), title, str(occurred or "")),
                repository_id=repo_id, kind=EventKind.DOC_CREATED.value,
                source_kind=SourceKind.NOTES.value, source_ref=str(path),
                occurred_at=_iso(occurred), title=title, body=body,
                tags=item.get("tags", []), importance=float(item.get("importance", 0.5)),
            )
            store.upsert_event(evt)
            count += 1

    return {"repository_id": repo_id, "notes": count}


# ---------------------------------------------------------------------------
# Chat conversations (adapter)
# ---------------------------------------------------------------------------

def ingest_conversations(store: Store, conversations: list[Conversation], repo_id: str = "default") -> dict:
    """Ingest parsed chat conversations as sessions + chat_message events.

    This adapts the existing chat-parsing pipeline into the historian
    model. Each conversation becomes a Session; each message becomes an
    Event. Decisions/bugs/fixes extracted inline are tagged.
    """
    from .extract import extract_from_conversation, summarize
    _ensure_repo(store, repo_id, name=repo_id)
    sessions = 0
    events = 0
    for idx, conv in enumerate(conversations, start=1):
        session_id = _stable_id("session", repo_id, conv.provider, conv.raw_id) or _stable_id("session", repo_id, str(idx))
        occurred = conv.created or conv.updated
        summary = summarize(conv)
        store.upsert_session(Session(
            id=session_id, repository_id=repo_id, provider=conv.provider,
            source_ref=conv.source_file, title=conv.title or "(untitled)",
            created_at=_iso(conv.created), updated_at=_iso(conv.updated),
            project="", message_count=len(conv.messages), summary=summary,
        ))
        store.upsert_event(Event(
            id=_stable_id("event", "chat_session", session_id),
            repository_id=repo_id, kind=EventKind.CHAT_SESSION.value,
            source_kind=conv.provider, source_ref=conv.source_file,
            occurred_at=_iso(occurred), ended_at=_iso(conv.updated),
            title=conv.title or "(untitled)", body=summary,
            detail_id=session_id, importance=0.5,
        ))
        sessions += 1

        ext = extract_from_conversation(conv)
        for mi, msg in enumerate(conv.messages):
            eid = _stable_id("event", "chat_message", session_id, str(mi))
            actor_id = _stable_id("person", "chat", conv.provider, msg.role)
            store.upsert_person(Person(id=actor_id, name=msg.role or "unknown", role=msg.role))
            tags: list[str] = []
            if msg.role == "user":
                tags.append("prompt")
            else:
                tags.append("response")
            # Attach extraction hints as tags
            for key in ("decisions", "bugs", "fixes", "architecture", "open_questions"):
                if any(token in msg.content.lower() for token in _HINTS[key]):
                    tags.append(key.rstrip("s"))
            store.upsert_event(Event(
                id=eid, repository_id=repo_id, kind=EventKind.CHAT_MESSAGE.value,
                source_kind=conv.provider, source_ref=conv.source_file,
                occurred_at=_iso(msg.timestamp or occurred),
                actor_id=actor_id, title=(msg.content[:120] + "…") if len(msg.content) > 120 else msg.content,
                body=msg.content, detail_id=session_id, tags=tags, importance=0.4 + (0.1 if msg.role != "user" else 0.0),
            ))
            events += 1

    return {"repository_id": repo_id, "sessions": sessions, "events": events}


_HINTS = {
    "decisions": ["decided", "choosing", "chose", "adopted", "agreed"],
    "bugs": ["bug", "error", "failing", "crash", "broken"],
    "fixes": ["fixed", "resolved", "patched", "corrected"],
    "architecture": ["architecture", "refactor", "restructured", "module"],
    "open_questions": ["should we", "how should", "question", "unclear"],
}


# ---------------------------------------------------------------------------
# GitHub PRs/issues (JSON exports)
# ---------------------------------------------------------------------------

def ingest_github_export(store: Store, path: str | Path, repo_id: str) -> dict:
    """Ingest a GitHub PR/issue export (JSON).

    Accepts:
      - A list of issue/PR objects
      - A single issue/PR object
      - {"items": [...]} wrapper
    Each item should have at least `number`, `title`, `state`, `user`, `created_at`.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    if isinstance(data, dict):
        data = data.get("items") or [data]
    if not isinstance(data, list):
        return {"repository_id": repo_id, "github": 0}
    count = 0
    for item in data:
        if not isinstance(item, dict):
            continue
        num = item.get("number")
        title = item.get("title", "")
        state = (item.get("state") or "").lower()
        user = item.get("user") or {}
        actor_id = _stable_id("person", str(user.get("login") or user.get("id") or "unknown").lower())
        if user.get("login"):
            store.upsert_person(Person(id=actor_id, name=user.get("login", ""), username=user.get("login", ""), role="author"))
        occurred = _parse_iso(item.get("created_at"))
        updated = _parse_iso(item.get("updated_at") or item.get("closed_at"))
        is_pr = bool(item.get("pull_request") or item.get("merged_at") or "pr" in title.lower())
        if is_pr and state == "closed" and item.get("merged_at"):
            kind = EventKind.PR_MERGED.value
        elif is_pr:
            kind = EventKind.PR_OPENED.value
        elif state == "closed":
            kind = EventKind.ISSUE_CLOSED.value
        else:
            kind = EventKind.ISSUE_OPENED.value

        body = item.get("body") or ""
        artifact = Artifact(
            id=_stable_id("artifact", "pr" if is_pr else "issue", repo_id, str(num)),
            repository_id=repo_id,
            kind=ArtifactKind.PR.value if is_pr else ArtifactKind.ISSUE.value,
            ref=str(num), title=title, path="", created_at=_iso(occurred),
            author_id=actor_id,
            metadata={"state": state, "labels": [l.get("name") for l in (item.get("labels") or []) if isinstance(l, dict)]},
        )
        store.upsert_artifact(artifact)
        store.upsert_event(Event(
            id=_stable_id("event", kind, repo_id, str(num)),
            repository_id=repo_id, kind=kind, source_kind=SourceKind.GITHUB.value,
            source_ref=str(path), occurred_at=_iso(occurred), ended_at=_iso(updated),
            actor_id=actor_id, title=title, body=body[:4000], detail_id=artifact.id,
            tags=[l for l in artifact.metadata.get("labels", []) or []],
            importance=0.75 if is_pr else 0.6,
        ))
        count += 1
    return {"repository_id": repo_id, "github": count}

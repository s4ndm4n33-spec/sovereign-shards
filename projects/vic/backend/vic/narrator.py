"""Narrative generator: produce human-readable reports from linked events.

Generates several report kinds:
  - executive_summary
  - architectural_evolution
  - dependency_evolution
  - state_of_project (at a point in time)
  - decision_tree
  - custom (from a natural-language query)

Narratives cite events by id, so every claim is traceable back to a
source event. Generated narratives are persisted to the store so they
can be retrieved and compared over time.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from .historian_model import Narrative, Event
from .store import Store
from .timeline import build_timeline, answer_question

log = logging.getLogger("vic.narrator")


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_date(s: Optional[str]) -> str:
    if not s:
        return "unknown"
    try:
        return s[:10]
    except (TypeError, ValueError):
        return "unknown"


def generate_executive_summary(store: Store, repository_id: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None) -> Narrative:
    tl = build_timeline(store, repository_id=repository_id, since=since, until=until, limit=5000)
    events = tl["events"]
    decisions = store.list_decisions(repository_id=repository_id)
    milestones = store.list_milestones(repository_id=repository_id)
    persons = store.list_persons(repository_id=repository_id)
    artifacts = store.list_artifacts(repository_id=repository_id)

    period = tl.get("period") or {}
    start, end = _fmt_date(period.get("start")), _fmt_date(period.get("end"))

    lines: list[str] = []
    lines.append(f"# Executive Summary")
    lines.append(f"\n**Repository:** {repository_id or 'all'}")
    lines.append(f"**Period:** {start} to {end}")
    lines.append(f"\nThis report spans {len(events)} events, {len(decisions)} decisions, "
                 f"{len(milestones)} milestones, {len(artifacts)} artifacts, and {len(persons)} contributors.")

    if decisions:
        lines.append("\n## Key Decisions\n")
        for d in decisions[:15]:
            lines.append(f"- **{_fmt_date(d.get('decided_at'))}** — {d['title']} ({d.get('status', 'unknown')})")

    if milestones:
        lines.append("\n## Milestones\n")
        for m in milestones[:10]:
            lines.append(f"- **{_fmt_date(m.get('achieved_at'))}** — {m['name']} ({m.get('kind', '')})")

    # Top contributors
    if persons:
        lines.append("\n## Contributors\n")
        for p in persons[:10]:
            name = p.get("name") or p.get("username") or p.get("email") or p.get("id")
            lines.append(f"- {name}")

    body = "\n".join(lines)
    n = Narrative(
        id=_stable_id("narrative", "exec_summary", repository_id or "all", since or "", until or ""),
        repository_id=repository_id or "",
        title="Executive Summary",
        body=body,
        kind="executive_summary",
        period_start=since,
        period_end=until,
        event_ids=[e["id"] for e in events[:50]],
        citations=[{"event_id": e["id"], "title": e.get("title", ""), "occurred_at": e.get("occurred_at")} for e in events[:50]],
        generated_at=_now(),
    )
    store.upsert_narrative(n)
    return n


def generate_architectural_evolution(store: Store, repository_id: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None) -> Narrative:
    """Trace architecture-related events chronologically."""
    events = store.list_events(repository_id=repository_id, since=since, until=until, limit=5000)
    arch_events = [e for e in events if "architecture" in (e.get("tags") or []) or "refactor" in (e.get("tags") or []) or e.get("kind") == "decision"]
    arch_events.sort(key=lambda e: e.get("occurred_at") or "")

    lines: list[str] = []
    lines.append("# Architectural Evolution")
    lines.append(f"\n**Repository:** {repository_id or 'all'}")
    lines.append(f"**Period:** {_fmt_date(since)} to {_fmt_date(until)}")
    lines.append(f"\n{len(arch_events)} architecture-related events detected.\n")

    # Group by month for evolution phases
    by_month: dict[str, list[dict]] = defaultdict(list)
    for e in arch_events:
        ts = e.get("occurred_at") or "unknown"
        month = ts[:7] if len(ts) >= 7 else "unknown"
        by_month[month].append(e)

    for month in sorted(by_month.keys()):
        lines.append(f"## {month}")
        for e in by_month[month]:
            lines.append(f"- **[{e.get('kind', '')}]** {_fmt_date(e.get('occurred_at'))} — {e.get('title', '')}")
            if e.get("body"):
                snippet = e["body"][:200].replace("\n", " ")
                lines.append(f"  > {snippet}…")
        lines.append("")

    body = "\n".join(lines)
    n = Narrative(
        id=_stable_id("narrative", "arch_evolution", repository_id or "all", since or "", until or ""),
        repository_id=repository_id or "",
        title="Architectural Evolution",
        body=body,
        kind="arch_evolution",
        period_start=since,
        period_end=until,
        event_ids=[e["id"] for e in arch_events],
        citations=[{"event_id": e["id"], "title": e.get("title", ""), "occurred_at": e.get("occurred_at")} for e in arch_events[:50]],
        generated_at=_now(),
    )
    store.upsert_narrative(n)
    return n


def generate_dependency_evolution(store: Store, repository_id: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None) -> Narrative:
    """Track dependency-related changes via commit/doc events mentioning deps."""
    events = store.list_events(repository_id=repository_id, since=since, until=until, limit=5000)
    dep_events = [e for e in events if _is_dep_related(e)]
    dep_events.sort(key=lambda e: e.get("occurred_at") or "")

    lines: list[str] = []
    lines.append("# Dependency Evolution")
    lines.append(f"\n**Repository:** {repository_id or 'all'}")
    lines.append(f"**Period:** {_fmt_date(since)} to {_fmt_date(until)}")
    lines.append(f"\n{len(dep_events)} dependency-related events detected.\n")

    # Track dependencies mentioned
    dep_mentions: dict[str, list[str]] = defaultdict(list)
    for e in dep_events:
        for dep in _extract_deps(e.get("body") or e.get("title") or ""):
            dep_mentions[dep].append(e.get("occurred_at", ""))

    lines.append("## Dependencies Tracked\n")
    for dep in sorted(dep_mentions.keys()):
        dates = dep_mentions[dep]
        lines.append(f"- **{dep}** — {len(dates)} mention(s), first: {_fmt_date(dates[0]) if dates else 'unknown'}")

    lines.append("\n## Timeline of Dependency Changes\n")
    for e in dep_events:
        lines.append(f"- **{_fmt_date(e.get('occurred_at'))}** [{e.get('kind', '')}] — {e.get('title', '')}")

    body = "\n".join(lines)
    n = Narrative(
        id=_stable_id("narrative", "dep_evolution", repository_id or "all", since or "", until or ""),
        repository_id=repository_id or "",
        title="Dependency Evolution",
        body=body,
        kind="dep_evolution",
        period_start=since,
        period_end=until,
        event_ids=[e["id"] for e in dep_events],
        citations=[{"event_id": e["id"], "title": e.get("title", ""), "occurred_at": e.get("occurred_at")} for e in dep_events[:50]],
        generated_at=_now(),
    )
    store.upsert_narrative(n)
    return n


def generate_state_of_project(store: Store, repository_id: Optional[str] = None, at_date: Optional[str] = None) -> Narrative:
    """Snapshot the project state at a point in time."""
    events = store.list_events(repository_id=repository_id, until=at_date, limit=10000)
    events.sort(key=lambda e: e.get("occurred_at") or "")

    lines: list[str] = []
    lines.append(f"# State of the Project")
    lines.append(f"\n**Repository:** {repository_id or 'all'}")
    lines.append(f"**As of:** {_fmt_date(at_date)}")
    lines.append(f"\n{len(events)} events recorded up to this point.\n")

    kinds: dict[str, int] = defaultdict(int)
    for e in events:
        kinds[e.get("kind", "unknown")] += 1
    lines.append("## Activity Breakdown\n")
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        lines.append(f"- {k}: {v}")

    decisions = [e for e in events if e.get("kind") == "decision"]
    if decisions:
        lines.append("\n## Decisions to Date\n")
        for d in decisions[:10]:
            lines.append(f"- **{_fmt_date(d.get('occurred_at'))}** — {d.get('title', '')}")

    # Most recent commits/docs
    recent = events[-10:]
    lines.append("\n## Most Recent Activity\n")
    for e in reversed(recent):
        lines.append(f"- **{_fmt_date(e.get('occurred_at'))}** [{e.get('kind', '')}] — {e.get('title', '')}")

    # Contributors active up to this point
    actors = {e.get("actor_id") for e in events if e.get("actor_id")}
    lines.append(f"\n## Contributors\n{len(actors)} contributor(s) active through {_fmt_date(at_date)}.")

    body = "\n".join(lines)
    n = Narrative(
        id=_stable_id("narrative", "state", repository_id or "all", at_date or ""),
        repository_id=repository_id or "",
        title=f"State of the Project — {_fmt_date(at_date)}",
        body=body,
        kind="state_of_project",
        period_start=None,
        period_end=at_date,
        event_ids=[e["id"] for e in events[:50]],
        citations=[{"event_id": e["id"], "title": e.get("title", ""), "occurred_at": e.get("occurred_at")} for e in events[:50]],
        generated_at=_now(),
    )
    store.upsert_narrative(n)
    return n


def generate_decision_tree(store: Store, repository_id: Optional[str] = None) -> Narrative:
    """Build a tree of decisions showing supersession lineage."""
    decisions = store.list_decisions(repository_id=repository_id)
    decisions.sort(key=lambda d: d.get("decided_at") or "")

    lines: list[str] = []
    lines.append("# Decision Tree")
    lines.append(f"\n**Repository:** {repository_id or 'all'}")
    lines.append(f"\n{len(decisions)} decisions recorded.\n")

    # Build parent → children map
    by_id = {d["id"]: d for d in decisions}
    children: dict[str, list[dict]] = defaultdict(list)
    roots: list[dict] = []
    for d in decisions:
        parent = d.get("superseded_by")
        if parent and parent in by_id:
            children[parent].append(d)
        else:
            roots.append(d)

    def _render(node: dict, depth: int = 0):
        indent = "  " * depth
        status = node.get("status", "unknown")
        marker = "✓" if status == "accepted" else ("⊘" if status in ("superseded", "rejected") else "?")
        lines.append(f"{indent}- {marker} **{_fmt_date(node.get('decided_at'))}** — {node['title']} [{status}]")
        if node.get("rationale"):
            lines.append(f"{indent}  > {node['rationale'][:150]}…")
        for child in children.get(node["id"], []):
            _render(child, depth + 1)

    for root in roots:
        _render(root)

    body = "\n".join(lines)
    n = Narrative(
        id=_stable_id("narrative", "decision_tree", repository_id or "all"),
        repository_id=repository_id or "",
        title="Decision Tree",
        body=body,
        kind="decision_tree",
        event_ids=[d["id"] for d in decisions],
        citations=[{"decision_id": d["id"], "title": d["title"], "decided_at": d.get("decided_at")} for d in decisions],
        generated_at=_now(),
    )
    store.upsert_narrative(n)
    return n


def generate_from_query(store: Store, question: str, repository_id: Optional[str] = None) -> Narrative:
    """Generate a narrative answer to a natural-language historical question."""
    answer = answer_question(store, question, repository_id=repository_id)
    events = answer.get("events", [])

    lines: list[str] = []
    lines.append(f"# Query: {question}")
    lines.append(f"\n{answer.get('answer', '')}")
    if events:
        lines.append("\n## Supporting Events\n")
        for e in events:
            lines.append(f"- **{_fmt_date(e.get('occurred_at'))}** [{e.get('kind', '')}] — {e.get('title', '')}")
            if e.get("body"):
                snippet = e["body"][:200].replace("\n", " ")
                lines.append(f"  > {snippet}…")

    body = "\n".join(lines)
    n = Narrative(
        id=_stable_id("narrative", "query", question, repository_id or ""),
        repository_id=repository_id or "",
        title=question,
        body=body,
        kind="custom",
        query=question,
        event_ids=[e["id"] for e in events],
        citations=[{"event_id": e["id"], "title": e.get("title", ""), "occurred_at": e.get("occurred_at")} for e in events],
        generated_at=_now(),
    )
    store.upsert_narrative(n)
    return n


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEP_KEYWORDS = ("dependency", "dependencies", "package", "upgrade", "bump", "install", "npm", "pip", "cargo", "requirements", "package.json", "cargo.toml", "lock file")


def _is_dep_related(event: dict) -> bool:
    text = (event.get("title") or "" + " " + (event.get("body") or "")).lower()
    return any(kw in text for kw in _DEP_KEYWORDS)


_DEP_RE = __import__("re").compile(r"\b([a-z][a-z0-9_-]{2,}[a-z])\s*(?:==|>=|<=|~=|@|to\s+|from\s+|added|removed|upgraded|bumped)", __import__("re").IGNORECASE)


def _extract_deps(text: str) -> list[str]:
    return [m.group(1).lower() for m in _DEP_RE.finditer(text)]

"""Timeline engine: chronologically link related events across sources.

The engine queries Events from the store, orders them by time, and infers
links between events based on shared attributes:

  - same actor (who-bridging)
  - shared tags or repository
  - direct `links` field references
  - semantic similarity above a threshold (TF-IDF cosine)

It also produces clusters — groups of related events forming a narrative
arc — and can answer historical questions like "what changed between X
and Y?" or "who introduced pattern Z?".
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from .store import Store

log = logging.getLogger("vic.timeline")


def build_timeline(
    store: Store,
    repository_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    kinds: Optional[list[str]] = None,
    limit: int = 1000,
) -> dict:
    """Return a chronological timeline with linked events.

    Output shape::

        {
          "events": [...],
          "links": [{"source": id, "target": id, "reason": "..."}],
          "clusters": [{"id": "...", "title": "...", "event_ids": [...]}],
          "actors": {actor_id: count},
          "period": {"start": ..., "end": ...},
        }
    """
    raw_events = store.list_events(repository_id=repository_id, since=since, until=until, limit=limit)
    if kinds:
        kindset = set(kinds)
        raw_events = [e for e in raw_events if e.get("kind") in kindset]

    if not raw_events:
        return {"events": [], "links": [], "clusters": [], "actors": {}, "period": None}

    # Sort chronologically
    events = sorted(raw_events, key=lambda e: e.get("occurred_at") or "")

    # Build links: shared actor, shared tags, explicit links, semantic similarity
    links: list[dict] = []
    by_actor: dict[str, list[str]] = defaultdict(list)
    by_tag: dict[str, list[str]] = defaultdict(list)
    for e in events:
        if e.get("actor_id"):
            by_actor[e["actor_id"]].append(e["id"])
        for t in e.get("tags") or []:
            by_tag[t].append(e["id"])

    # Actor-based links: consecutive events by same actor
    for actor, ids in by_actor.items():
        ids_sorted = sorted(ids, key=lambda i: next((e.get("occurred_at") for e in events if e["id"] == i), ""))
        for i in range(len(ids_sorted) - 1):
            links.append({"source": ids_sorted[i], "target": ids_sorted[i + 1], "reason": f"same actor ({actor})"})

    # Tag-based links: events sharing a tag
    for tag, ids in by_tag.items():
        if len(ids) < 2:
            continue
        # Connect nearest temporal neighbors within the tag group
        indexed = [(i, next((e.get("occurred_at") for e in events if e["id"] == i), "")) for i in ids]
        indexed.sort(key=lambda x: x[1])
        for i in range(len(indexed) - 1):
            links.append({"source": indexed[i][0], "target": indexed[i + 1][0], "reason": f"shared tag: {tag}"})

    # Explicit link references
    for e in events:
        for target in (e.get("links") or []):
            links.append({"source": e["id"], "target": target, "reason": "explicit"})

    # Clusters: group events within N hours sharing tags or actor
    clusters = _cluster_events(events, gap_hours=24)

    # Actor summary
    actor_counts: dict[str, int] = defaultdict(int)
    for e in events:
        if e.get("actor_id"):
            actor_counts[e["actor_id"]] += 1

    period = {
        "start": events[0].get("occurred_at"),
        "end": events[-1].get("occurred_at"),
    }

    return {
        "events": events,
        "links": _dedupe_links(links),
        "clusters": clusters,
        "actors": dict(actor_counts),
        "period": period,
    }


def _dedupe_links(links: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []
    for l in links:
        key = (l["source"], l["target"], l["reason"])
        rkey = (l["target"], l["source"], l["reason"])
        if key in seen or rkey in seen:
            continue
        seen.add(key)
        out.append(l)
    return out


def _cluster_events(events: list[dict], gap_hours: int = 24) -> list[dict]:
    """Group events into clusters based on temporal proximity and shared tags."""
    if not events:
        return []
    clusters: list[dict] = []
    current: list[dict] = []
    current_tags: set[str] = set()

    def _flush():
        if not current:
            return
        tag_str = ", ".join(sorted(current_tags)[:3]) or "general"
        title = f"{current[0].get('occurred_at', '')[:10]} — {tag_str}"
        clusters.append({
            "id": f"cluster-{len(clusters)}",
            "title": title,
            "event_ids": [e["id"] for e in current],
        })

    for e in events:
        ts = e.get("occurred_at")
        e_tags = set(e.get("tags") or [])
        if not current:
            current = [e]
            current_tags = e_tags
            continue
        prev_ts = current[-1].get("occurred_at")
        if ts and prev_ts:
            try:
                dt_prev = datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))
                dt_curr = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                gap = (dt_curr - dt_prev).total_seconds() / 3600.0
            except (ValueError, TypeError):
                gap = 999.0
        else:
            gap = 999.0
        overlap = current_tags & e_tags
        if gap <= gap_hours or overlap:
            current.append(e)
            current_tags |= e_tags
        else:
            _flush()
            current = [e]
            current_tags = e_tags
    _flush()
    return clusters


# ---------------------------------------------------------------------------
# Historical questions
# ---------------------------------------------------------------------------

def answer_question(store: Store, question: str, repository_id: Optional[str] = None) -> dict:
    """Answer a natural-language-style historical question.

    Pattern-matches on the question phrasing and dispatches to the
    appropriate timeline/search query. Returns a structured answer with
    supporting events.
    """
    q = question.lower().strip()

    # "why did X change between A and B"
    if "why" in q and "change" in q:
        return _why_changed(store, question, repository_id)
    # "who introduced/pushed/added X"
    if q.startswith("who ") or "who introduced" in q or "who pushed" in q or "who added" in q:
        return _who_did(store, question, repository_id)
    # "when did we first discuss X"
    if "when did" in q and ("first" in q or "discuss" in q or "introduce" in q):
        return _when_first(store, question, repository_id)
    # "what happened between A and B"
    if "between" in q and ("what" in q or "show" in q):
        return _what_between(store, question, repository_id)

    # Fallback: semantic search
    results = store.search_semantic(question, repository_id=repository_id, limit=10)
    return {
        "question": question,
        "answer": f"Found {len(results)} semantically related events.",
        "kind": "semantic",
        "events": results,
    }


def _extract_dates(question: str) -> tuple[Optional[str], Optional[str]]:
    import re
    months = r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    # YYYY-MM-DD
    m = re.findall(r"(20\d{2}-\d{2}-\d{2})", question)
    if len(m) >= 2:
        return m[0], m[1]
    elif len(m) == 1:
        return m[0], None
    # Month names
    m = re.findall(rf"{months}\s+20\d{{2}}", question, re.IGNORECASE)
    if len(m) >= 2:
        first = _month_to_iso(m[0])
        second = _month_to_iso(m[1])
        if first and second:
            return first, second
    return None, None


def _month_to_iso(month_year: str) -> Optional[str]:
    import re
    months = ["january","february","march","april","may","june","july","august","september","october","november","december"]
    m = re.search(r"([a-z]+)\s+(20\d{2})", month_year.lower())
    if not m:
        return None
    name, year = m.group(1), m.group(2)
    if name not in months:
        return None
    month_num = months.index(name) + 1
    return f"{year}-{month_num:02d}-01"


def _extract_keywords(question: str) -> list[str]:
    """Extract query keywords from a question, stripping common question words."""
    stopwords = set("why who when did we first discuss introduced between what show the a an of to in on at and or by was were is are you me our us them".split())
    import re
    tokens = re.findall(r"[a-z][a-z0-9_-]+", question.lower())
    return [t for t in tokens if t not in stopwords and len(t) > 2]


def _why_changed(store: Store, question: str, repository_id: Optional[str]) -> dict:
    since, until = _extract_dates(question)
    keywords = _extract_keywords(question)
    query = " ".join(keywords[:8]) or question
    events = store.list_events(repository_id=repository_id, since=since, until=until, limit=200)
    # Refine to events semantically related to the keywords
    if keywords:
        sem = store.search_semantic(query, repository_id=repository_id, limit=30)
        sem_ids = {e["id"] for e in sem}
        events = [e for e in events if e["id"] in sem_ids] or events
    events.sort(key=lambda e: e.get("occurred_at") or "")
    decisions = [e for e in events if e.get("kind") == "decision"]
    answer = _narrate_changes(events, decisions, since or "the period start", until or "the period end")
    return {
        "question": question,
        "answer": answer,
        "kind": "why_changed",
        "events": events[:20],
        "period": {"start": since, "end": until},
    }


def _who_did(store: Store, question: str, repository_id: Optional[str]) -> dict:
    keywords = _extract_keywords(question)
    query = " ".join(keywords[:8])
    results = store.search_semantic(query, repository_id=repository_id, limit=20)
    results.sort(key=lambda e: e.get("occurred_at") or "")
    if not results:
        return {"question": question, "answer": f"No events found matching '{query}'.", "kind": "who", "events": []}
    first = results[0]
    actor_id = first.get("actor_id")
    actor = _person_name(store, actor_id) if actor_id else "unknown"
    occurred = first.get("occurred_at", "unknown")
    answer = f"The earliest matching event was by {actor} on {occurred}: \"{first.get('title', '')}\"."
    return {
        "question": question,
        "answer": answer,
        "kind": "who",
        "events": results[:10],
        "actor": actor,
        "first_seen": occurred,
    }


def _when_first(store: Store, question: str, repository_id: Optional[str]) -> dict:
    keywords = _extract_keywords(question)
    query = " ".join(keywords[:8])
    results = store.search_semantic(query, repository_id=repository_id, limit=20)
    results.sort(key=lambda e: e.get("occurred_at") or "")
    if not results:
        return {"question": question, "answer": f"No events found matching '{query}'.", "kind": "when", "events": []}
    first = results[0]
    answer = f"First discussed on {first.get('occurred_at', 'unknown')}: \"{first.get('title', '')}\"."
    return {
        "question": question,
        "answer": answer,
        "kind": "when",
        "events": results[:10],
    }


def _what_between(store: Store, question: str, repository_id: Optional[str]) -> dict:
    since, until = _extract_dates(question)
    events = store.list_events(repository_id=repository_id, since=since, until=until, limit=200)
    tl = build_timeline(store, repository_id=repository_id, since=since, until=until, limit=200)
    answer = _narrate_changes(events, [e for e in events if e.get("kind") == "decision"], since or "start", until or "end")
    return {
        "question": question,
        "answer": answer,
        "kind": "what_between",
        "events": events[:20],
        "timeline": tl,
        "period": {"start": since, "end": until},
    }


def _person_name(store: Store, person_id: str) -> str:
    persons = store.list_persons()
    for p in persons:
        if p.get("id") == person_id:
            return p.get("name") or p.get("username") or p.get("email") or person_id
    return person_id


def _narrate_changes(events: list[dict], decisions: list[dict], start: str, end: str) -> str:
    if not events:
        return f"No events found between {start} and {end}."
    parts: list[str] = []
    parts.append(f"Between {start} and {end}, {len(events)} events were recorded.")
    kinds: dict[str, int] = defaultdict(int)
    for e in events:
        kinds[e.get("kind", "unknown")] += 1
    kind_summary = ", ".join(f"{k} ({v})" for k, v in sorted(kinds.items(), key=lambda x: -x[1])[:5])
    parts.append(f"Event breakdown: {kind_summary}.")
    if decisions:
        parts.append(f"Key decisions in this window:")
        for d in decisions[:5]:
            parts.append(f"  - {d.get('occurred_at', '')[:10]}: {d.get('title', '')}")
    # Highlight high-importance events
    important = [e for e in events if (e.get("importance") or 0) >= 0.7]
    if important:
        parts.append(f"\nNotable events ({len(important)} highlighted):")
        for e in important[:8]:
            parts.append(f"  - {e.get('occurred_at', '')[:10]} [{e.get('kind', '')}]: {e.get('title', '')}")
    return "\n".join(parts)

"""Local embedded store for V.I.C. — SQLite, sovereign by design.

All data lives in a single file on the user's machine (default
`~/.vic/historian.db`). No cloud, no remote service. The store owns:

  - schema creation + migrations
  - upserts for every entity type
  - event retrieval for timeline + semantic indexing
  - FTS5 full-text index alongside a manual TF-IDF term index used
    for semantic similarity search.

The FTS5 virtual table is the primary search backend; TF-IDF + cosine
similarity is layered on top for semantic ranking of related events.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .historian_model import (
    Artifact,
    Decision,
    Event,
    Milestone,
    Narrative,
    Person,
    Repository,
    Session,
    to_dict,
)

log = logging.getLogger("vic.store")

DEFAULT_DB_PATH = Path(os.environ.get("VIC_DB_PATH", str(Path.home() / ".vic" / "historian.db")))

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_STOP = set(
    "the a an and or but if then else for to of in on at by with from as is it this that these those i you he she we they me him her us them my your his hers our their".split()
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    name TEXT,
    url TEXT,
    default_branch TEXT,
    description TEXT,
    language TEXT,
    first_seen TEXT,
    last_seen TEXT,
    extra TEXT
);

CREATE TABLE IF NOT EXISTS persons (
    id TEXT PRIMARY KEY,
    name TEXT,
    email TEXT,
    username TEXT,
    role TEXT,
    first_seen TEXT,
    last_seen TEXT,
    aliases TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    repository_id TEXT,
    provider TEXT,
    source_ref TEXT,
    title TEXT,
    created_at TEXT,
    updated_at TEXT,
    project TEXT,
    message_count INTEGER,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    repository_id TEXT,
    title TEXT,
    rationale TEXT,
    status TEXT,
    scope TEXT,
    decided_at TEXT,
    decided_by TEXT,
    superseded_by TEXT,
    tags TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    repository_id TEXT,
    kind TEXT,
    ref TEXT,
    title TEXT,
    path TEXT,
    created_at TEXT,
    author_id TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS milestones (
    id TEXT PRIMARY KEY,
    repository_id TEXT,
    name TEXT,
    description TEXT,
    achieved_at TEXT,
    kind TEXT,
    tags TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    repository_id TEXT,
    kind TEXT,
    source_kind TEXT,
    source_ref TEXT,
    occurred_at TEXT,
    ended_at TEXT,
    actor_id TEXT,
    title TEXT,
    body TEXT,
    detail_id TEXT,
    tags TEXT,
    links TEXT,
    importance REAL,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_repo_time ON events(repository_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_kind, source_ref);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor_id);

CREATE TABLE IF NOT EXISTS narratives (
    id TEXT PRIMARY KEY,
    repository_id TEXT,
    title TEXT,
    body TEXT,
    kind TEXT,
    period_start TEXT,
    period_end TEXT,
    query TEXT,
    event_ids TEXT,
    citations TEXT,
    generated_at TEXT
);

-- Full-text search over event title + body
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    event_id UNINDEXED,
    repository_id UNINDEXED,
    kind UNINDEXED,
    title,
    body,
    tokenize='porter unicode61'
);

-- TF-IDF term index for semantic similarity
CREATE TABLE IF NOT EXISTS term_doc (
    term TEXT,
    event_id TEXT,
    count INTEGER,
    PRIMARY KEY (term, event_id)
);

CREATE INDEX IF NOT EXISTS idx_term_doc_term ON term_doc(term);
CREATE INDEX IF NOT EXISTS idx_term_doc_event ON term_doc(event_id);

CREATE TABLE IF NOT EXISTS doc_len (
    event_id TEXT PRIMARY KEY,
    length INTEGER
);

CREATE TABLE IF NOT EXISTS doc_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class Store:
    """Thread-safe wrapper around a SQLite file."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or DEFAULT_DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    # -- connection management ------------------------------------------------

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(str(self.path), timeout=30.0, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            try:
                yield conn
            finally:
                conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            cur = conn.execute("SELECT value FROM doc_meta WHERE key='schema_version'")
            row = cur.fetchone()
            version = int(row["value"]) if row else 0
            if version < 1:
                conn.execute("INSERT OR REPLACE INTO doc_meta(key,value) VALUES('schema_version','1')")
                log.info("Initialised V.I.C. store at %s", self.path)

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _stable_id(*parts: str) -> str:
        raw = "|".join(str(p) for p in parts).encode("utf-8")
        return hashlib.sha1(raw).hexdigest()[:16]

    @staticmethod
    def _j(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _unj(value: Optional[str], default: Any = None) -> Any:
        if not value:
            return default if default is not None else None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else value

    # -- repositories ---------------------------------------------------------

    def upsert_repository(self, repo: Repository) -> str:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO repositories(id,name,url,default_branch,description,language,first_seen,last_seen,extra)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name, url=excluded.url, default_branch=excluded.default_branch,
                     description=excluded.description, language=excluded.language,
                     last_seen=excluded.last_seen, extra=excluded.extra""",
                (repo.id, repo.name, repo.url, repo.default_branch, repo.description,
                 repo.language, repo.first_seen, repo.last_seen, self._j({})),
            )
        return repo.id

    # -- persons --------------------------------------------------------------

    def upsert_person(self, person: Person) -> str:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO persons(id,name,email,username,role,first_seen,last_seen,aliases)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=CASE WHEN excluded.name != '' THEN excluded.name ELSE persons.name END,
                     email=CASE WHEN excluded.email != '' THEN excluded.email ELSE persons.email END,
                     username=CASE WHEN excluded.username != '' THEN excluded.username ELSE persons.username END,
                     role=CASE WHEN excluded.role != '' THEN excluded.role ELSE persons.role END,
                     last_seen=excluded.last_seen, aliases=excluded.aliases""",
                (person.id, person.name, person.email, person.username, person.role,
                 person.first_seen, person.last_seen, self._j(person.aliases)),
            )
        return person.id

    # -- sessions -------------------------------------------------------------

    def upsert_session(self, s: Session) -> str:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO sessions(id,repository_id,provider,source_ref,title,created_at,updated_at,project,message_count,summary)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     title=excluded.title, updated_at=excluded.updated_at,
                     project=excluded.project, message_count=excluded.message_count,
                     summary=excluded.summary""",
                (s.id, s.repository_id, s.provider, s.source_ref, s.title, s.created_at,
                 s.updated_at, s.project, s.message_count, s.summary),
            )
        return s.id

    # -- decisions ------------------------------------------------------------

    def upsert_decision(self, d: Decision) -> str:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO decisions(id,repository_id,title,rationale,status,scope,decided_at,decided_by,superseded_by,tags)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     title=excluded.title, rationale=excluded.rationale, status=excluded.status,
                     scope=excluded.scope, decided_at=excluded.decided_at, decided_by=excluded.decided_by,
                     superseded_by=excluded.superseded_by, tags=excluded.tags""",
                (d.id, d.repository_id, d.title, d.rationale, d.status, d.scope,
                 d.decided_at, d.decided_by, d.superseded_by, self._j(d.tags)),
            )
        return d.id

    # -- artifacts ------------------------------------------------------------

    def upsert_artifact(self, a: Artifact) -> str:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO artifacts(id,repository_id,kind,ref,title,path,created_at,author_id,metadata)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     kind=excluded.kind, ref=excluded.ref, title=excluded.title, path=excluded.path,
                     created_at=excluded.created_at, author_id=excluded.author_id, metadata=excluded.metadata""",
                (a.id, a.repository_id, a.kind, a.ref, a.title, a.path, a.created_at,
                 a.author_id, self._j(a.metadata)),
            )
        return a.id

    # -- milestones -----------------------------------------------------------

    def upsert_milestone(self, m: Milestone) -> str:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO milestones(id,repository_id,name,description,achieved_at,kind,tags)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name, description=excluded.description, achieved_at=excluded.achieved_at,
                     kind=excluded.kind, tags=excluded.tags""",
                (m.id, m.repository_id, m.name, m.description, m.achieved_at, m.kind, self._j(m.tags)),
            )
        return m.id

    # -- events --------------------------------------------------------------

    def upsert_event(self, e: Event) -> str:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO events(id,repository_id,kind,source_kind,source_ref,occurred_at,ended_at,
                       actor_id,title,body,detail_id,tags,links,importance,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     repository_id=excluded.repository_id, kind=excluded.kind,
                     source_kind=excluded.source_kind, source_ref=excluded.source_ref,
                     occurred_at=excluded.occurred_at, ended_at=excluded.ended_at,
                     actor_id=excluded.actor_id, title=excluded.title, body=excluded.body,
                     detail_id=excluded.detail_id, tags=excluded.tags, links=excluded.links,
                     importance=excluded.importance""",
                (e.id, e.repository_id, e.kind, e.source_kind, e.source_ref, e.occurred_at,
                 e.ended_at, e.actor_id, e.title, e.body, e.detail_id,
                 self._j(e.tags), self._j(e.links), e.importance, e.created_at),
            )
            self._index_event_fts(conn, e)
            self._index_event_tfidf(conn, e)
        return e.id

    def _index_event_fts(self, conn: sqlite3.Connection, e: Event) -> None:
        conn.execute("DELETE FROM events_fts WHERE event_id=?", (e.id,))
        conn.execute(
            "INSERT INTO events_fts(event_id,repository_id,kind,title,body) VALUES (?,?,?,?,?)",
            (e.id, e.repository_id, e.kind, e.title, e.body),
        )

    def _index_event_tfidf(self, conn: sqlite3.Connection, e: Event) -> None:
        conn.execute("DELETE FROM term_doc WHERE event_id=?", (e.id,))
        conn.execute("DELETE FROM doc_len WHERE event_id=?", (e.id,))
        tokens = [t for t in _TOKEN_RE.findall((e.title + " " + e.body).lower()) if t not in _STOP]
        if not tokens:
            return
        counts = Counter(tokens)
        for term, count in counts.items():
            conn.execute(
                "INSERT OR REPLACE INTO term_doc(term,event_id,count) VALUES (?,?,?)",
                (term, e.id, count),
            )
        conn.execute(
            "INSERT OR REPLACE INTO doc_len(event_id,length) VALUES (?,?)",
            (e.id, len(tokens)),
        )

    # -- narratives -----------------------------------------------------------

    def upsert_narrative(self, n: Narrative) -> str:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO narratives(id,repository_id,title,body,kind,period_start,period_end,query,event_ids,citations,generated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     title=excluded.title, body=excluded.body, kind=excluded.kind,
                     period_start=excluded.period_start, period_end=excluded.period_end,
                     query=excluded.query, event_ids=excluded.event_ids,
                     citations=excluded.citations, generated_at=excluded.generated_at""",
                (n.id, n.repository_id, n.title, n.body, n.kind, n.period_start, n.period_end,
                 n.query, self._j(n.event_ids), self._j(n.citations), n.generated_at),
            )
        return n.id

    # -- queries --------------------------------------------------------------

    def list_repositories(self) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM repositories ORDER BY last_seen DESC")]

    def get_repository(self, repo_id: str) -> Optional[dict]:
        with self.connect() as conn:
            r = conn.execute("SELECT * FROM repositories WHERE id=?", (repo_id,)).fetchone()
            return dict(r) if r else None

    def list_events(
        self,
        repository_id: Optional[str] = None,
        kind: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict]:
        q = "SELECT * FROM events WHERE 1=1"
        args: list[Any] = []
        if repository_id:
            q += " AND repository_id=?"
            args.append(repository_id)
        if kind:
            q += " AND kind=?"
            args.append(kind)
        if since:
            q += " AND occurred_at >= ?"
            args.append(since)
        if until:
            q += " AND occurred_at <= ?"
            args.append(until)
        q += " ORDER BY COALESCE(occurred_at,'') ASC, importance DESC LIMIT ?"
        args.append(limit)
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(q, args)]
        for r in rows:
            r["tags"] = self._unj(r.get("tags"), [])
            r["links"] = self._unj(r.get("links"), [])
        return rows

    def list_decisions(self, repository_id: Optional[str] = None) -> list[dict]:
        q = "SELECT * FROM decisions"
        args: list[Any] = []
        if repository_id:
            q += " WHERE repository_id=?"
            args.append(repository_id)
        q += " ORDER BY COALESCE(decided_at,'') ASC"
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(q, args)]
        for r in rows:
            r["tags"] = self._unj(r.get("tags"), [])
        return rows

    def list_artifacts(self, repository_id: Optional[str] = None, kind: Optional[str] = None) -> list[dict]:
        q = "SELECT * FROM artifacts WHERE 1=1"
        args: list[Any] = []
        if repository_id:
            q += " AND repository_id=?"
            args.append(repository_id)
        if kind:
            q += " AND kind=?"
            args.append(kind)
        q += " ORDER BY COALESCE(created_at,'') ASC"
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(q, args)]
        for r in rows:
            r["metadata"] = self._unj(r.get("metadata"), {})
        return rows

    def list_milestones(self, repository_id: Optional[str] = None) -> list[dict]:
        q = "SELECT * FROM milestones"
        args: list[Any] = []
        if repository_id:
            q += " WHERE repository_id=?"
            args.append(repository_id)
        q += " ORDER BY COALESCE(achieved_at,'') ASC"
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(q, args)]
        for r in rows:
            r["tags"] = self._unj(r.get("tags"), [])
        return rows

    def list_persons(self, repository_id: Optional[str] = None) -> list[dict]:
        q = "SELECT * FROM persons"
        args: list[Any] = []
        if repository_id:
            q += " WHERE id IN (SELECT DISTINCT actor_id FROM events WHERE repository_id=?)"
            args.append(repository_id)
        q += " ORDER BY COALESCE(last_seen,'') DESC"
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(q, args)]
        for r in rows:
            r["aliases"] = self._unj(r.get("aliases"), [])
        return rows

    def list_narratives(self, repository_id: Optional[str] = None) -> list[dict]:
        q = "SELECT * FROM narratives"
        args: list[Any] = []
        if repository_id:
            q += " WHERE repository_id=?"
            args.append(repository_id)
        q += " ORDER BY generated_at DESC"
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(q, args)]
        for r in rows:
            r["event_ids"] = self._unj(r.get("event_ids"), [])
            r["citations"] = self._unj(r.get("citations"), [])
        return rows

    def stats(self) -> dict:
        with self.connect() as conn:
            counts: dict[str, int] = {}
            for table in ("repositories", "persons", "sessions", "decisions", "artifacts", "milestones", "events", "narratives"):
                r = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
                counts[table] = r["c"]
            r = conn.execute("SELECT MIN(occurred_at) AS lo, MAX(occurred_at) AS hi FROM events WHERE occurred_at IS NOT NULL").fetchone()
            counts["earliest"] = r["lo"]
            counts["latest"] = r["hi"]
        return counts

    # -- semantic search -----------------------------------------------------

    def search_fulltext(self, query: str, repository_id: Optional[str] = None, limit: int = 30) -> list[dict]:
        """FTS5 keyword search ranked by BM25."""
        q = "SELECT e.*, bm25(events_fts) AS score FROM events_fts JOIN events e ON events_fts.event_id = e.id WHERE events_fts MATCH ?"
        args: list[Any] = [query]
        if repository_id:
            q += " AND e.repository_id=?"
            args.append(repository_id)
        q += " ORDER BY score ASC LIMIT ?"
        args.append(limit)
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(q, args)]
        for r in rows:
            r["tags"] = self._unj(r.get("tags"), [])
            r["links"] = self._unj(r.get("links"), [])
        return rows

    def search_semantic(self, query: str, repository_id: Optional[str] = None, limit: int = 20) -> list[dict]:
        """TF-IDF cosine-similarity search.

        Ranks events by cosine similarity between the query vector and each
        event's TF-IDF vector. Falls back to FTS5 if the term index is empty.
        """
        tokens = [t for t in _TOKEN_RE.findall(query.lower()) if t not in _STOP]
        if not tokens:
            return self.search_fulltext(query, repository_id, limit)

        with self.connect() as conn:
            # Compute IDF across the corpus
            total_docs = conn.execute("SELECT COUNT(DISTINCT event_id) AS c FROM term_doc").fetchone()["c"]
            if total_docs == 0:
                return self.search_fulltext(query, repository_id, limit)

            # Query term frequencies
            q_counts = Counter(tokens)
            q_vec: dict[str, float] = {}
            for term, count in q_counts.items():
                df_row = conn.execute("SELECT COUNT(DISTINCT event_id) AS c FROM term_doc WHERE term=?", (term,)).fetchone()
                df = df_row["c"]
                if df == 0:
                    continue
                idf = max(1.0, (1.0 + total_docs) / (1.0 + df))
                q_vec[term] = (1.0 + (count / max(1, len(tokens)))) * idf

            if not q_vec:
                return self.search_fulltext(query, repository_id, limit)

            q_norm = sum(v * v for v in q_vec.values()) ** 0.5
            if q_norm == 0:
                return self.search_fulltext(query, repository_id, limit)

            # Gather candidate docs that contain any query term
            placeholders = ",".join("?" for _ in q_vec)
            repo_clause = " AND repository_id=?" if repository_id else ""
            args: list[Any] = list(q_vec.keys())
            if repository_id:
                args.append(repository_id)
            candidates_sql = f"""
                SELECT td.event_id, td.term, td.count, COALESCE(dl.length,1) AS len
                FROM term_doc td
                LEFT JOIN doc_len dl ON dl.event_id = td.event_id
                JOIN events e ON e.id = td.event_id
                WHERE td.term IN ({placeholders}){repo_clause}
            """
            # NOTE: e.* not fetched here; we fetch event rows after ranking
            scores: dict[str, float] = defaultdict(float)
            doc_norms: dict[str, float] = defaultdict(float)

            events_in_scope = {row["event_id"] for row in conn.execute(
                f"SELECT id AS event_id FROM events WHERE 1=1{(' AND repository_id=?' if repository_id else '')}",
                ([repository_id] if repository_id else []),
            )} if repository_id else None

            for row in conn.execute(candidates_sql, args):
                eid = row["event_id"]
                term = row["term"]
                if term not in q_vec:
                    continue
                # event TF = count / doc length; idf reused from query
                total_docs_local = total_docs
                df_row = conn.execute("SELECT COUNT(DISTINCT event_id) AS c FROM term_doc WHERE term=?", (term,)).fetchone()
                df = df_row["c"]
                idf = max(1.0, (1.0 + total_docs_local) / (1.0 + df))
                tf = row["count"] / max(1, row["len"])
                weight = tf * idf
                scores[eid] += q_vec[term] * weight
                doc_norms[eid] += weight * weight

            ranked: list[tuple[float, str]] = []
            for eid, dot in scores.items():
                dn = (doc_norms[eid] ** 0.5) or 1.0
                sim = dot / (q_norm * dn)
                ranked.append((sim, eid))
            ranked.sort(reverse=True)
            top_ids = [eid for _, eid in ranked[:limit]]
            if not top_ids:
                return self.search_fulltext(query, repository_id, limit)

            placeholders_in = ",".join("?" for _ in top_ids)
            rows = [dict(r) for r in conn.execute(
                f"SELECT * FROM events WHERE id IN ({placeholders_in})",
                top_ids,
            )]
            # Attach similarity and sort by it
            score_map = {eid: sim for sim, eid in ranked}
            for r in rows:
                r["similarity"] = score_map.get(r["id"], 0.0)
                r["tags"] = self._unj(r.get("tags"), [])
                r["links"] = self._unj(r.get("links"), [])
            id_index = {eid: i for i, eid in enumerate(top_ids)}
            rows.sort(key=lambda r: id_index.get(r["id"], 999))
            return rows

    def find_related(self, event_id: str, limit: int = 10) -> list[dict]:
        """Find events related to a given event by shared tags, actor, or semantic similarity."""
        with self.connect() as conn:
            base = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            if not base:
                return []
            base = dict(base)
            base_tags = self._unj(base.get("tags"), [])
            base_links = self._unj(base.get("links"), [])

            # Explicitly linked events
            related: list[dict] = []
            if base_links:
                placeholders = ",".join("?" for _ in base_links)
                for r in conn.execute(f"SELECT * FROM events WHERE id IN ({placeholders})", base_links):
                    related.append(dict(r))

            # Shared tags
            if base_tags:
                like_clauses = " OR ".join("tags LIKE ?" for _ in base_tags)
                like_args = [f'%"{t}"%' for t in base_tags]
                rows = conn.execute(
                    f"SELECT * FROM events WHERE id != ? AND ({like_clauses}) ORDER BY importance DESC LIMIT ?",
                    [event_id, *like_args, limit * 2],
                )
                seen = {event_id, *[r["id"] for r in related]}
                for r in rows:
                    if r["id"] in seen:
                        continue
                    related.append(dict(r))
                    seen.add(r["id"])

            # Semantic via TF-IDF on the event's own body
            if len(related) < limit:
                sem = self.search_semantic(base.get("body") or base.get("title") or "", repository_id=base.get("repository_id"), limit=limit)
                seen = {event_id, *[r["id"] for r in related]}
                for r in sem:
                    if r["id"] in seen:
                        continue
                    related.append(r)
                    seen.add(r["id"])
                    if len(related) >= limit:
                        break

        for r in related[:limit]:
            r["tags"] = self._unj(r.get("tags"), [])
            r["links"] = self._unj(r.get("links"), [])
        return related[:limit]

    def reset(self) -> None:
        """Drop all data. Used by tests and `vic reset`."""
        with self.connect() as conn:
            for table in ("repositories","persons","sessions","decisions","artifacts","milestones","events","events_fts","term_doc","doc_len","narratives"):
                conn.execute(f"DELETE FROM {table}")

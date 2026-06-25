# V.I.C. — Full Specification Sheet

## 1. System Identity

| Field | Value |
|---|---|
| Name | V.I.C. (Value In Conversation) |
| Type | Local-first sovereign chat archive processor + automated software historian |
| Backend | Python 3, Flask 3.x, SQLite (WAL mode), reportlab, selenium |
| Frontend | React 18, TypeScript 5, Vite 5, Tailwind CSS 3 |
| Runtime | Single-process Flask on `127.0.0.1:8001` |
| Data store | `~/.vic/historian.db` (SQLite, overridable via `VIC_DB_PATH`) |
| Cloud dependency | None — fully sovereign by design |

---

## 2. Backend Modules

### 2.1 `models.py` — Data Models

| Class | Fields | Purpose |
|---|---|---|
| `Message` | `role: str`, `content: str`, `timestamp: datetime \| None` | Single chat message |
| `Conversation` | `provider: str`, `source_file: str`, `raw_id: str`, `title: str`, `created: datetime`, `updated: datetime`, `messages: list[Message]` | A parsed conversation session |
| `Conversation.date_iso()` | → `str` | ISO date string or `"unknown"` |

### 2.2 `detect.py` — Provider Auto-Detection

| Function | Signature | Logic |
|---|---|---|
| `detect_provider` | `(zip_path: Path \| None = None, file_path: Path \| None = None, content: str \| None = None) → set[str]` | Sniffs ZIP contents / file headers / text to return provider set: `{"chatgpt"}`, `{"claude"}`, `{"gemini"}`, or `{"unknown"}` |

**Heuristics**:
- ChatGPT: `conversations.json` present, or `"mapping"` + `"author"` in content
- Claude: `"chat_messages"` or `"sender"` or `"claude"` in content
- Gemini: Takeout `My Activity/Gemini/` path, or `"My Activity"` + `"Gemini"`

### 2.3 `parsers.py` — Provider Parsers

| Function | Input | Output |
|---|---|---|
| `parse_chatgpt_file` | `Path` to `conversations.json` | `list[Conversation]` |
| `parse_claude_file` | `Path` to Claude JSON | `list[Conversation]` |
| `parse_gemini_file` | `Path` to Gemini `MyActivity.json` | `list[Conversation]` |
| `extract_conversations_from_zip` | `Path` to ZIP | `list[Conversation]` |
| `parse_directory` | `Path` to directory | `list[Conversation]` |

**ChatGPT parser**: Walks the `mapping` DAG, extracts messages in topological order (root → children), filters `user`/`assistant` roles, reads `content.parts[]`.

**Claude parser**: Reads `chat_messages[]` with `sender` (`human`/`assistant`) and `text`.

**Gemini parser**: Reads `events[]` from Takeout format, groups by `title` (conversation title), extracts `subtitles[].text` as assistant responses.

### 2.4 `extract.py` — Keyword Extraction

| Function | Signature | Output |
|---|---|---|
| `extract_from_conversation` | `(conv: Conversation) → dict` | `{"decisions": [...], "bugs": [...], "fixes": [...], "architecture": [...], "open_questions": [...]}` |
| `summarize` | `(conv: Conversation, max_sentences: int = 3) → str` | First N sentences of conversation |
| `extract_themes` | `(conversations: list[Conversation]) → list[tuple[str, int]]` | Top keywords by frequency across all conversations |
| `group_by_project` | `(conversations) → dict[str, list[Conversation]]` | Groups by extracted project label |
| `timeline` | `(conversations) → list[Conversation]` | Sorts by `created` date |

**Extraction patterns** (deterministic, keyword-based):
- Decisions: `"we decided"`, `"let's use"`, `"chose to"`, `"will adopt"`
- Bugs: `"bug"`, `"crash"`, `"error"`, `"broken"`, `"fails"`
- Fixes: `"fixed"`, `"resolved"`, `"patched"`, `"corrected"`
- Architecture: `"architecture"`, `"refactor"`, `"module"`, `"interface"`, `"pattern"`
- Open questions: `"should we"`, `"open question"`, `"?"`

### 2.5 `pipeline.py` — Processing Pipeline

| Function | Signature | Output |
|---|---|---|
| `process_inputs` | `(zip_paths: list[Path], json_paths: list[Path]) → ProcessResult` | Full pipeline result |
| `process_conversations` | `(conversations: list[Conversation]) → ProcessResult` | Process parsed conversations |

**`ProcessResult` dataclass**:
```
providers: list[str]
session_count: int
message_count: int
date_range: tuple[str, str]
themes: list[tuple[str, int]]
projects: dict[str, list[dict]]
sessions: list[dict]
jsonl: str
exec_summary: str
ir: dict | None
```

**Pipeline flow**:
1. Parse ZIPs (`_parse_zip`) and JSON files (`_parse_files`)
2. Deduplicate by `(provider, raw_id)`
3. Sort chronologically (`timeline`)
4. Extract per-session metadata (`extract_from_conversation`)
5. Extract cross-session themes (`extract_themes`)
6. Group by project (`group_by_project`)
7. Build JSONL (`build_jsonl`)
8. Generate executive summary
9. Run `DeterministicAgent.process()` to produce IR

### 2.6 `output.py` — Output Writers

| Function | Signature | Output |
|---|---|---|
| `build_jsonl` | `(conversations: list[Conversation]) → str` | JSONL text (one entry per session) |
| `parse_jsonl` | `(text: str) → list[dict]` | Parsed entries |
| `build_pdf` | `(conversations: list[Conversation], project_title: str) → bytes` | PDF bytes (reportlab) |

**PDF structure**: Title block → Executive Summary → Key Decisions (dated) → Problems & Resolutions → Per-session detail (title, date, summary, decisions, bugs, fixes, open questions).

### 2.7 `crawler.py` — Shared Chat Crawler

| Function | Signature | Output |
|---|---|---|
| `crawl_chat_url` | `(url: str) → Conversation` | Parsed conversation from share page |
| `detect_provider_from_url` | `(url: str) → str` | Provider string |

**Crawl logic**: Uses `selenium` with a headless browser to render share pages, then extracts messages:
- ChatGPT: `div[data-message-author-role]` elements
- Claude: `div.font-user` / `div.font-claude` elements

**Error class**: `CrawlError(reason: str)`

### 2.8 `store.py` — SQLite Store

**Schema** (7 tables + FTS5 + TF-IDF index):

| Table | Primary Key | Key Fields |
|---|---|---|
| `repositories` | `id` | name, url, default_branch, language |
| `persons` | `id` | name, email, username, role, aliases |
| `sessions` | `id` | repository_id, provider, source_ref, title, message_count |
| `decisions` | `id` | repository_id, title, rationale, status, decided_at, decided_by, superseded_by |
| `artifacts` | `id` | repository_id, kind, ref, title, path, author_id |
| `milestones` | `id` | repository_id, name, achieved_at, kind |
| `events` | `id` | repository_id, kind, source_kind, source_ref, occurred_at, actor_id, title, body, tags, links, importance |
| `narratives` | `id` | repository_id, title, body, kind, period_start, period_end, query, event_ids, citations |
| `edges` | `id` | source_node, target_node, relationship_type, confidence, rationale, provenance |
| `events_fts` | FTS5 virtual | event_id, repository_id, kind, title, body (porter unicode61 tokenizer) |
| `term_doc` | `(term, event_id)` | count — TF-IDF term index |
| `doc_len` | `event_id` | length — document length for TF-IDF |
| `doc_meta` | `key` | value — metadata KV |

**Store class API**:
- `__init__(path: Path | None)` — creates `~/.vic/historian.db`, runs schema
- `connect()` — context manager, thread-safe (RLock), WAL mode, `foreign_keys=ON`
- `upsert_repository`, `upsert_person`, `upsert_session`, `upsert_decision`, `upsert_artifact`, `upsert_milestone`, `upsert_event`, `upsert_narrative`, `upsert_edge`
- `list_repositories`, `list_persons`, `list_events`, `list_decisions`, `list_artifacts`, `list_milestones`, `list_narratives`, `list_edges`
- `stats()` — aggregate counts
- `search_fulltext(q, repository_id, limit)` — FTS5 search
- `search_semantic(q, repository_id, limit)` — TF-IDF cosine similarity
- `_reindex_event(event_id)` — updates FTS5 + TF-IDF for an event

### 2.9 `ingest.py` — Ingestion Functions

| Function | Input | Output |
|---|---|---|
| `ingest_git` | `(store, repo_path: Path, repo_id, limit=5000)` | `{"repository_id": ..., "commits": N}` |
| `ingest_markdown` | `(store, path: Path, repo_id)` | `{"repository_id": ..., "title": ..., "decision": bool}` |
| `ingest_structured_notes` | `(store, path: Path, repo_id)` | `{"repository_id": ..., "notes": N}` |
| `ingest_github_export` | `(store, path: Path, repo_id)` | `{"repository_id": ..., "issues": N, "prs": N}` |
| `ingest_conversations` | `(store, conversations: list[Conversation], repo_id)` | `{"repository_id": ..., "sessions": N, "events": N}` |

**Git ingestion**: Runs `git log --format=...` via subprocess, parses commit metadata (hash, author, date, message), creates events for each commit. Detects conventional-commit prefixes (`feat:`, `fix:`, `refactor:`, etc.) for event kind classification.

**Markdown ingestion**: Parses YAML frontmatter (title, date, author, tags, scope), detects ADR pattern (`## Decision`, `## Status`), creates a decision event if ADR detected.

**Notes ingestion**: Reads JSON with `decisions[]` and `milestones[]` arrays, upserts each.

### 2.10 `timeline.py` — Timeline + Q&A

| Function | Signature | Output |
|---|---|---|
| `build_timeline` | `(store, repository_id, since, until, kinds, limit) → dict` | `{"events": [...], "links": [...], "clusters": [...], "actors": {...}, "period": {...}}` |
| `answer_question` | `(store, question, repository_id) → dict` | `{"question": ..., "answer": ..., "kind": ..., "events": [...], "actor": ..., "first_seen": ..., "period": {...}}` |

**Timeline links**: Events sharing tags or entities are linked with a `reason` string.

**Timeline clusters**: Events are grouped into temporal clusters by date proximity.

**Q&A**: Uses semantic search to find relevant events, then generates a deterministic answer string. Detects "who introduced" / "when did we first" patterns.

### 2.11 `narrator.py` — Narrative Generators

| Function | Kind | Output |
|---|---|---|
| `generate_executive_summary` | `executive_summary` | Narrative with key decisions, milestones, contributors |
| `generate_architectural_evolution` | `arch_evolution` | Narrative tracing architecture events by month |
| `generate_dependency_evolution` | `dep_evolution` | Narrative tracing dependency changes |
| `generate_state_of_project` | `state_of_project` | Snapshot at a specific date |
| `generate_decision_tree` | `decision_tree` | Hierarchical decision tree |
| `generate_from_query` | `custom` | Custom query-based narrative |

All return `Narrative` objects (from `historian_model.py`) with `body` (markdown), `event_ids` (cited events), and `citations` (event_id + title + occurred_at).

### 2.12 `historian_model.py` — Historian Data Models

| Dataclass | Key Fields |
|---|---|
| `Repository` | id, name, url, default_branch, language |
| `Person` | id, name, email, username, role, aliases |
| `Session` | id, repository_id, provider, source_ref, title, message_count |
| `Decision` | id, repository_id, title, rationale, status, decided_at, decided_by, superseded_by, tags |
| `Artifact` | id, repository_id, kind, ref, title, path, author_id |
| `Milestone` | id, repository_id, name, achieved_at, kind, tags |
| `Event` | id, repository_id, kind, source_kind, source_ref, occurred_at, ended_at, actor_id, title, body, detail_id, tags, links, importance |
| `Narrative` | id, repository_id, title, body, kind, period_start, period_end, query, event_ids, citations, generated_at |

`to_dict(obj)` — serializes any dataclass to dict.

### 2.13 `graph_model.py` — Graph Types

| Class/Enum | Purpose |
|---|---|
| `EdgeType` (Enum) | IMPLEMENTS, SUPERSEDES, MOTIVATED, INSPIRED, CONTAINS, DOCUMENTS, REFERENCES, DISCUSSES, DEPENDS_ON, PRECEDES, FOLLOWS, REVERSES, REFINES, RESOLVES, REPLACES |
| `Edge` (dataclass) | source_node, target_node, relationship_type, confidence, rationale, provenance, created_at; `.id` (sha1 hash), `.to_dict()` |
| `Claim` (dataclass) | subject, predicate, obj, evidence, confidence, inference_rule, derived_at; `.to_dict()` |

### 2.14 `knowledge_graph.py` — Graph Builder

**Current implementation** (intent reducer):
- `__init__(store=None)` — ignores `store`, initializes `self.nodes: Dict[str, Dict]`, `self.edges: List[Dict]`
- `apply(intents)` — processes `ADD_NODE`, `ADD_EDGE`, `UPDATE_NODE`, `DELETE_NODE` intents
- `get_node(node_id)`, `get_edges()` — read-only helpers

### 2.15 `biography.py` — Concept Biography

| Function | Signature | Output |
|---|---|---|
| `generate_biography` | `(kg, concept: str, repository_id) → dict` | `{"found": bool, "concept": ..., "first_mention": {...}, "current_status": ..., "stats": {...}, "claims": [...]}` |

Traces a concept through the knowledge graph: first mention, all mentions, current status, and claims with evidence chains.

### 2.16 `evolution.py` — Evolution Queries

| Function | Query ID | Output |
|---|---|---|
| `reversed_decisions` | `reversed_decisions` | Decisions later superseded/reversed |
| `architectural_churn` | `architectural_churn` | Modules with most architectural change |
| `discussed_not_implemented` | `discussed_not_implemented` | Ideas discussed but never coded |
| `conversations_to_code` | `conversations_to_code` | Chats that resulted in implementations |
| `decision_impact` | `decision_impact` | Decisions with greatest downstream impact |
| `top_contributors` | `top_contributors` | Most influential contributors |
| `run_evolution_query` | dispatch | Routes query string to the correct function |

### 2.17 `narrative_engine.py` — Narrative Arcs

| Class | Purpose |
|---|---|
| `NarrativeBlock` (dataclass) | arc_id, time_range, title, story, entities, provenance |
| `NarrativeEngine` | Builds temporal arcs from intents + sessions; segments into 5-event chunks; renders story blocks |

### 2.18 `causal_graph.py` — Causal Reconstruction

| Class | Purpose |
|---|---|
| `CausalGraph` | Builds transition counts between entities across narrative arcs; tracks cross-session invariants via `edge_stats` |

### 2.19 `temporal_query.py` — Temporal DSL

| Class | Methods |
|---|---|
| `TemporalQueryEngine` | `find_first_occurrence(entity)`, `trace_entity_lifecycle(entity)`, `reconstruct_at_arc(arc_id)`, `causal_chain(entity)` |

### 2.20 `ingestion_adapter.py` — IR Translator

| Class | Purpose |
|---|---|
| `IngestionAdapter` | Converts raw multi-session chat JSON into strict IR: `{"intents": [...]}` with `ADD_NODE`/`ADD_EDGE` ops |

---

## 3. Frontend Specification

### 3.1 Component Tree

```
App
├── ArchiveView (stage: idle → working → done/error)
│   ├── Dropzone
│   ├── LinkInput
│   ├── ProgressBar
│   ├── ResultsPanel
│   │   ├── SessionCard[]
│   │   └── Download buttons (PDF, JSONL)
│   └── FeatureGrid
└── HistorianView
    ├── HistorianDashboard (stats + repositories)
    ├── IngestionPanel (git, markdown, notes)
    ├── SearchPanel (semantic + fulltext)
    ├── TimelineView
    ├── NarrativeReader
    ├── GraphExplorer
    ├── BiographyPanel
    └── EvolutionPanel
```

### 3.2 API Client Layer

| File | Exports |
|---|---|
| `api.ts` | `processFiles`, `crawlUrls`, `downloadPdf`, `downloadJsonl` |
| `archive-api.ts` | Duplicate of `api.ts` (same exports) |
| `history-api.ts` | `api` object with `stats`, `timeline`, `search`, `ask`, `narrative`, `narratives`, `decisions`, `persons`, `ingestGit`, `ingestMarkdown`, `ingestNotes` |
| `types.ts` | `Provider`, `SessionEntry`, `ProcessResult`, `ApiError` |

### 3.3 Design System

| Token | Value |
|---|---|
| `ink-950` | `#070B14` (darkest bg) |
| `ink-900` | `#0B1020` |
| `ink-800` | `#111827` |
| `ink-700` | `#1F2937` |
| `ink-600` | `#374151` |
| `ink-500` | `#4B5563` |
| `ink-300` | `#9CA3AF` |
| `ink-100` | `#D1D5DB` (lightest text) |
| `vic-glow` | `#22D3EE` (cyan accent) |
| `vic-accent` | `#14B8A6` (teal accent) |
| `vic-warn` | `#F59E0B` (amber) |
| `vic-err` | `#EF4444` (red) |
| Font sans | Inter |
| Font mono | JetBrains Mono |
| Shadow glow | `0 0 0 1px rgba(34,211,238,0.25), 0 8px 30px -8px rgba(34,211,238,0.35)` |

---

## 4. Schemas

### 4.1 `entity.json`
- Required: `entity_id`, `type`, `surface_forms`
- `type` enum: `PERSON`, `SYSTEM`, `EVENT`, `OBJECT`, `UNKNOWN`
- `additionalProperties: false`

### 4.2 `event.json`
- Required: `event_id`, `action`, `entities`
- Optional: `timestamp`, `confidence`, `source_span`
- `additionalProperties: false`

### 4.3 `intent.json`
- Required: `op`
- `op` enum: `ADD_NODE`, `ADD_EDGE`, `UPDATE_NODE`, `DELETE_NODE`, `UNRESOLVED`
- Optional: `node`, `from`, `to`, `relation`, `metadata`
- `additionalProperties: false`

### 4.4 `relation.json`
- Required: `from`, `to`, `relation`
- `relation` enum: `IS_A`, `PART_OF`, `CAUSES`, `PRECEDES`, `REFERENCES`, `CONTAINS`, `DERIVES_FROM`, `UNRESOLVED`
- Optional: `confidence`, `metadata`
- `additionalProperties: false`

---

## 5. Test Suite

| Test | File | Scope | Status |
|---|---|---|---|
| Pipeline e2e | `test_pipeline.py` | All 3 providers → PDF + JSONL | **BROKEN** (imports missing `make_pdf_bytes`, `result_to_dict`) |
| HTTP e2e | `test_http.py` | `/api/process`, `/api/pdf`, `/api/jsonl` | **BROKEN** (same import issue via `app.py`) |
| Crawler e2e | `test_crawler.py` | Fake share pages → `/api/crawl` | **BROKEN** (same import issue via `app.py`) |
| Historian V1 e2e | `test_historian.py` | Git + ADR + notes + chats → timeline + search + narratives + Q&A | **BROKEN** (same import issue via `app.py`) |
| Historian V2 e2e | `test_historian_v2.py` | Knowledge graph + biography + evolution + provenance | **BROKEN** (KnowledgeGraph API mismatch) |

---

## 6. Dependencies

### Backend (`requirements.txt`)
- `flask>=3.0` — HTTP server
- `reportlab>=4.0` — PDF generation
- `selenium>=4.20` — Headless browser for share-page crawling

### Frontend (`package.json`)
- `react@^18.3.1`, `react-dom@^18.3.1`
- `typescript@^5.5.4`
- `vite@^5.4.3`, `@vitejs/plugin-react@^4.3.1`
- `tailwindcss@^3.4.10`, `postcss@^8.4.45`, `autoprefixer@^10.4.20`

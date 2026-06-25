# V.I.C. — Value In Conversation

**V.I.C.** is a sovereign, local-first system with two modes:

1. **Chat Archive Processor** — Ingest bulk AI chat exports (ChatGPT, Claude, Gemini), auto-detect providers, merge sessions chronologically, extract decisions/bugs/fixes/open-questions, and export a structured PDF report plus machine-readable `archive.jsonl`.
2. **Automated Software Historian** — Ingest git repos, markdown ADRs, structured notes, and chat conversations into a local SQLite store, then query a chronological timeline, run semantic search, generate narrative reports, and explore a typed knowledge graph with provenance chains.

Everything runs locally. No cloud, no third-party uploads. Your prompts, code, and decisions stay on your machine.

---

## File Tree

```
projects/vic/
├── README.md                          ← this file
├── backend/
│   ├── requirements.txt               ← flask, reportlab, selenium
│   ├── tests/
│   │   ├── test_crawler.py            ← crawl fake share pages → /api/crawl
│   │   ├── test_historian.py          ← V1 historian e2e (git, ADR, notes, chats)
│   │   ├── test_historian_v2.py       ← V2 e2e (knowledge graph, biography, evolution)
│   │   ├── test_http.py               ← /api/process, /api/pdf, /api/jsonl
│   │   └── test_pipeline.py           ← pipeline e2e (all 3 providers → PDF + JSONL)
│   └── vic/
│       ├── __init__.py
│       ├── __main__.py                ← `python -m vic` → starts Flask on :8001
│       ├── app.py                     ← Flask app, all HTTP endpoints
│       ├── biography.py               ← concept biography + provenance claims
│       ├── causal_graph.py            ← deterministic causal reconstruction over arcs
│       ├── crawler.py                 ← crawl shared chat URLs (ChatGPT, Claude)
│       ├── detect.py                  ← provider auto-detection (zip/file heuristics)
│       ├── evolution.py               ← evolution queries (reversed decisions, churn, impact)
│       ├── extract.py                 ← keyword extraction (decisions, bugs, fixes, themes)
│       ├── graph_model.py             ← Edge, EdgeType, Claim dataclasses
│       ├── historian_model.py         ← Event, Decision, Milestone, Person, Narrative, etc.
│       ├── ingestion_adapter.py       ← raw chat JSON → IR intents
│       ├── ingest.py                  ← git/markdown/notes/github/chat ingestion → store
│       ├── knowledge_graph.py         ← graph builder (intent reducer)
│       ├── models.py                  ← Conversation, Message dataclasses
│       ├── narrative_engine.py        ← deterministic narrative arcs over timeline
│       ├── narrator.py                ← narrative report generators (exec summary, arch, etc.)
│       ├── output.py                  ← JSONL + PDF writers (reportlab)
│       ├── parsers.py                 ← ChatGPT/Claude/Gemini parsers
│       ├── pipeline.py                ← ingest → parse → extract → ProcessResult
│       ├── store.py                   ← SQLite store (schema, upserts, FTS5, TF-IDF, edges)
│       ├── temporal_query.py           ← temporal DSL over narrative arcs
│       └── timeline.py                ← timeline builder + Q&A answer_question
├── frontend/
│   ├── index.html
│   ├── package.json                   ← react 18, vite 5, tailwind 3
│   ├── postcss.config.js
│   ├── tailwind.config.js             ← ink + vic color ramps, Inter/JetBrains Mono
│   ├── tsconfig.json
│   ├── vite.config.ts                 ← proxy /api → 127.0.0.1:8001
│   └── src/
│       ├── App.tsx                    ← root: archive view + historian view
│       ├── index.css                  ← dark grid backdrop, animations
│       ├── main.tsx
│       ├── vite-env.d.ts
│       ├── components/
│       │   ├── BiographyPanel.tsx     ← concept biography query UI
│       │   ├── Dropzone.tsx           ← file upload dropzone
│       │   ├── EvolutionPanel.tsx     ← evolution query runner UI
│       │   ├── GraphExplorer.tsx      ← knowledge graph node explorer
│       │   ├── HistorianDashboard.tsx ← store stats + repositories
│       │   ├── IngestionPanel.tsx     ← git/markdown/notes ingestion UI
│       │   ├── LinkInput.tsx          ← shared chat URL input
│       │   ├── NarrativeReader.tsx    ← narrative generation + reader
│       │   ├── ProgressBar.tsx       ← upload/processing progress
│       │   ├── ProviderBadge.tsx      ← provider label chip
│       │   ├── ResultsPanel.tsx       ← archive results + PDF/JSONL download
│       │   ├── SearchPanel.tsx        ← semantic/fulltext search UI
│       │   ├── SessionCard.tsx        ← single session summary card
│       │   └── TimelineView.tsx       ← chronological timeline with links
│       └── lib/
│           ├── api.ts                 ← archive API (processFiles, crawlUrls, downloads)
│           ├── archive-api.ts          ← archive API (duplicate of api.ts)
│           ├── history-api.ts         ← historian API (stats, timeline, search, ask, narrative)
│           └── types.ts               ← ProcessResult, SessionEntry, Provider types
└── schemas/
    ├── entity.json                    ← entity schema (entity_id, type, surface_forms)
    ├── event.json                     ← event schema (event_id, action, entities, confidence)
    ├── intent.json                    ← graph intent schema (ADD_NODE, ADD_EDGE, etc.)
    └── relation.json                  ← relation schema (from, to, relation, confidence)
```

---

## Architecture

### Mode 1: Chat Archive Processor

```
Upload ZIPs/JSON ──► detect.py (provider auto-detect)
                ──► parsers.py (ChatGPT/Claude/Gemini parsers)
                ──► models.py (Conversation, Message)
                ──► extract.py (decisions, bugs, fixes, themes, summaries)
                ──► output.py (build_jsonl, build_pdf)
                ──► ProcessResult → frontend ResultsPanel
```

- **Auto-detect**: ZIP contents and file headers are sniffed to identify ChatGPT (`conversations.json` with `mapping`), Claude (`chat_messages` with `sender`), or Gemini (Takeout `MyActivity.json`).
- **Extraction**: Keyword-based deterministic extraction — no LLM calls. Decisions, bugs, fixes, architecture notes, and open questions are pulled from message text via pattern matching.
- **Exports**: PDF (reportlab) with executive summary, key decisions, problems/resolutions, and per-session detail. JSONL with one structured entry per session.

### Mode 2: Automated Software Historian

```
Ingest sources ──► ingest.py (git, markdown, notes, github, chats)
               ──► store.py (SQLite: events, decisions, milestones, persons, edges)
               ──► timeline.py (chronological timeline + links + clusters)
               ──► narrator.py (narrative reports)
               ──► knowledge_graph.py (typed edges, provenance)
               ──► biography.py / evolution.py (concept biographies, evolution queries)
```

- **Store**: Single SQLite file (`~/.vic/historian.db`). Schema includes repositories, persons, sessions, decisions, artifacts, milestones, events, narratives, edges, FTS5 virtual table, and TF-IDF term index.
- **Search**: FTS5 full-text + manual TF-IDF cosine similarity for semantic ranking.
- **Timeline**: Events are linked by shared entities/tags and clustered into temporal groups.
- **Narratives**: Executive summary, architectural evolution, dependency evolution, state-of-project, decision tree, and custom query narratives — all with cited event IDs.
- **Knowledge Graph (V2)**: Typed edges (IMPLEMENTS, SUPERSEDES, DISCUSSES, etc.) with confidence and provenance. Concept biographies trace first-mention → current status with evidence chains. Evolution queries detect reversed decisions, architectural churn, discussed-not-implemented, conversations-to-code, decision impact, and top contributors.

---

## Backend API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Liveness check |
| `/api/process` | POST | Upload ZIPs/JSON, process, return preview |
| `/api/crawl` | POST | Crawl shared chat URL(s), process, return preview |
| `/api/pdf` | POST | Render PDF from JSON body |
| `/api/jsonl` | POST | Return archive.jsonl from JSON body |
| `/api/stats` | GET | Store statistics |
| `/api/repositories` | GET | List repositories |
| `/api/persons` | GET | List persons |
| `/api/events` | GET | List events (filtered) |
| `/api/decisions` | GET | List decisions |
| `/api/artifacts` | GET | List artifacts |
| `/api/milestones` | GET | List milestones |
| `/api/timeline` | GET | Chronological timeline with links |
| `/api/search` | GET | Semantic/fulltext search |
| `/api/ask` | POST | Answer a historical question |
| `/api/narrative` | POST | Generate a narrative report |
| `/api/narratives` | GET | List generated narratives |
| `/api/ingest/git` | POST | Ingest a local git repo |
| `/api/ingest/markdown` | POST | Ingest a markdown ADR |
| `/api/ingest/notes` | POST | Ingest structured notes JSON |
| `/api/ingest/github` | POST | Ingest a GitHub PR/issue export |
| `/api/graph` | GET | Knowledge graph stats + node exploration |
| `/api/biography` | POST | Generate a concept biography |
| `/api/evolution` | POST | Run an evolution query |
| `/api/provenance` | GET | Evidence chain for an event |

---

## Running

### Backend

```bash
cd projects/vic/backend
pip install -r requirements.txt
python -m vic          # starts Flask on 127.0.0.1:8001
```

### Frontend

```bash
cd projects/vic/frontend
npm install
npm run dev            # Vite on :5173, proxies /api → :8001
```

### Tests

```bash
cd projects/vic/backend
python tests/test_pipeline.py        # archive pipeline e2e
python tests/test_http.py            # HTTP endpoints e2e
python tests/test_crawler.py         # crawler e2e
python tests/test_historian.py       # V1 historian e2e
python tests/test_historian_v2.py    # V2 knowledge graph e2e
```

---

## Design

- **Dark, sovereign aesthetic**: `ink` neutral ramp (950→100) with `vic` accent colors (glow cyan `#22D3EE`, accent teal `#14B8A6`, warn amber, err red).
- **Typography**: Inter (sans), JetBrains Mono (mono).
- **Backdrop**: Subtle radial-gradient grid with cyan/teal glow accents.
- **Micro-interactions**: Dropzone scale-on-drag, card hover lift, fade-in results, shimmer skeletons.
- **Responsive**: `max-w-6xl` container, grid breakpoints for feature cards and session lists.

---

## Sovereignty

- Chat-archive processing is **stateless** — temp dirs are deleted per request.
- The historian store uses a **local embedded SQLite file** on the user's machine.
- No cloud database, no remote telemetry, no third-party API calls.
- CORS is open (`*`) for localhost dev but the design is local-only.

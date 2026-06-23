# V.I.C. — Value In Conversation

A bulk AI chat archive tool that processes exported conversation history from multiple AI providers (Gemini, ChatGPT, Claude) into structured project documentation. **Sovereign by design**: no auth, no cloud storage, nothing persisted to a remote server. Process locally, download, done.

V.I.C. also operates as an **automated software historian**: it ingests git history, pull requests, issue discussions, design docs, and chat logs into a unified timeline, then generates executive summaries, architectural evolution reports, dependency tracking, decision trees, and "state of the project at point in time" reports. Ask it "Who introduced the registry pattern?" or "When did we first discuss JGPU?" and get cited, searchable historical facts instead of archaeology.

## Stack

- **Frontend**: React + Vite + Tailwind (dark theme)
- **Backend**: Python + Flask
- **PDF**: reportlab
- **JSONL**: stdlib `json`
- **Historian store**: local embedded SQLite (stdlib `sqlite3`) at `~/.vic/historian.db` — sovereign by design, never a cloud database
- **Semantic search**: FTS5 (BM25) + TF-IDF cosine similarity
- **Headless crawling**: Selenium + Chromium (for JS-rendered share pages)

## Layout

```
projects/vic/
├── backend/
│   ├── requirements.txt
│   ├── vic/
│   │   ├── __init__.py
│   │   ├── __main__.py         # entry: python3 -m vic
│   │   ├── app.py               # Flask app + endpoints
│   │   ├── detect.py            # provider auto-detection
│   │   ├── parsers.py           # Gemini / ChatGPT / Claude parsers
│   │   ├── extract.py           # keyword clustering + extraction
│   │   ├── pipeline.py          # ingest → parse → extract → preview
│   │   ├── output.py            # archive.jsonl + PDF report writers
│   │   └── models.py            # Conversation / Message dataclasses
│   └── tests/
│       ├── test_pipeline.py     # end-to-end smoke test (all 3 providers)
│       └── test_http.py         # HTTP-level smoke test
└── frontend/
    ├── package.json
    ├── vite.config.ts           # dev proxy → 127.0.0.1:8001
    ├── tailwind.config.js
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── index.css
        ├── lib/{api.ts, types.ts}
        └── components/
            ├── Dropzone.tsx
            ├── ProgressBar.tsx
            ├── ProviderBadge.tsx
            ├── ResultsPanel.tsx
            └── SessionCard.tsx
```

## Run

### Backend

```bash
cd projects/vic/backend
pip install -r requirements.txt
python3 -m vic            # serves http://127.0.0.1:8001
```

### Frontend

```bash
cd projects/vic/frontend
npm install
npm run dev               # serves http://127.0.0.1:5173 (proxies /api → 8001)
```

Open http://127.0.0.1:5173, drag a Takeout ZIP / ChatGPT `conversations.json` / Claude JSON files onto the dropzone, **or paste a shared chat link** below the dropzone, and download the PDF + JSONL.

### Tests

```bash
cd projects/vic/backend
python3 tests/test_pipeline.py     # full pipeline across Gemini + ChatGPT + Claude
python3 tests/test_http.py         # Flask endpoints via test client
python3 tests/test_crawler.py      # URL crawl + provider auto-detection
python3 tests/test_historian.py    # historian: git + markdown + notes + chats → timeline + search + narratives
```

## Data model (historian)

Every timestamped fact is an **Event** — the universal timeline atom:

| Entity | Purpose |
| --- | --- |
| `Event` | A timestamped fact (commit, chat message, decision, PR, release). The timeline atom. |
| `Person` | Human or bot that authored events (git author, chat participant, commenter) |
| `Repository` | A git repo or logical project that events belong to |
| `Session` | A chat conversation (ChatGPT/Claude/Gemini), normalized |
| `Decision` | An explicit decision with rationale, status, scope, supersession lineage |
| `Artifact` | A produced artifact (commit, PR, issue, doc, diagram, release) |
| `Milestone` | A named point in time (release, freeze, demo, EOL) |
| `Narrative` | A generated human-readable report spanning linked events |

## Ingestion sources

| Source | Endpoint | How |
| --- | --- | --- |
| Git commits | `POST /api/ingest/git` | Runs `git log` locally against a repo path |
| Markdown docs | `POST /api/ingest/markdown` | Front-matter + body; auto-detects decision records (ADRs) |
| Structured notes | `POST /api/ingest/notes` | JSON with decisions, milestones, or generic timeline notes |
| GitHub exports | `POST /api/ingest/github` | PR/issue JSON exports |
| Chat uploads | `POST /api/process` | Existing archive flow — also feeds the historian store |
| Chat URLs | `POST /api/crawl` | Crawls shared chat links |

## Timeline engine

`GET /api/timeline` returns events chronologically with inferred links based on:
- same actor (who-bridging)
- shared tags or repository
- explicit `links` references
- temporal proximity (events within 24h sharing tags form clusters)

## Semantic search

`GET /api/search?q=…&mode=semantic` — TF-IDF cosine similarity ranking with FTS5 (BM25) fallback. Indexed on event title + body.

## Historical Q&A

`POST /api/ask` — pattern-matches natural-language questions:
- "Who introduced X?" → finds earliest event matching X, returns actor + date
- "When did we first discuss X?" → finds first chronological mention
- "Why did X change between A and B?" → events in date range semantically filtered
- "Show me what happened between A and B" → timeline window + summary

## Narrative reports

`POST /api/narrative` generates:
- `executive_summary` — overview of events, decisions, milestones, contributors
- `arch_evolution` — architecture-related events grouped by month
- `dep_evolution` — dependency additions, removals, upgrades
- `state_of_project` — snapshot at a point in time
- `decision_tree` — decisions with supersession lineage
- `custom` — narrative from a natural-language query

All narratives cite supporting event IDs so every claim is traceable.

Detection is structural — no manual selection, no content execution:

| Provider | Marker |
| --- | --- |
| Gemini | `Takeout/...Gemini/...` ZIP member paths |
| ChatGPT | `conversations.json` (in ZIP or folder) or `"mapping"` + `"author"` JSON keys |
| Claude | `"chat_messages"` / `"sender"` JSON keys, or `claude_*` filenames |

## URL crawling

In addition to file uploads, V.I.C. can crawl a **shared chat link**:

- Paste a ChatGPT share (`chatgpt.com/share/…`), Claude share (`claude.ai/share/…`), or Gemini share (`gemini.google.com/share/…`) into the link input.
- The crawler first tries a lightweight HTTP fetch; if the page is JS-rendered it falls back to a headless Chromium render via Selenium.
- Provider is auto-detected from the URL host, with content-based refinement for mirrors/aliases.
- Multiple URLs can be crawled at once; partial failures are surfaced as warnings without blocking the successful ones.
- Crawled conversations run through the exact same pipeline (extract → cluster → preview → export) as uploaded files.

Crawl endpoint: `POST /api/crawl` with `{"url": "…"}` or `{"urls": ["…", "…"]}`.

## Output

### `archive.jsonl` (one entry per session)

```json
{"session": 1, "date": "2026-03-14", "provider": "chatgpt", "summary": "...", "decisions": ["..."], "bugs": ["..."], "fixes": ["..."], "open_questions": ["..."]}
```

### PDF report sections

- Project title and date range
- Executive summary
- Key decisions (dated, bulleted)
- Problems and resolutions
- Architecture evolution
- Open questions
- Recurring themes
- Per-session cliffnotes (one paragraph each)

## Sovereign guarantees

- No authentication — anyone with network access to localhost can use it
- No database — nothing is stored after the request returns
- No cloud storage — uploads land in a per-request temp dir deleted on response
- No third-party LLM calls — extraction is rule-based and deterministic

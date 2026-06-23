# V.I.C. — Value In Conversation

A bulk AI chat archive tool that processes exported conversation history from multiple AI providers (Gemini, ChatGPT, Claude) into structured project documentation. **Sovereign by design**: no auth, no database, no cloud storage, nothing persisted server-side. Process locally, download, done.

## Stack

- **Frontend**: React + Vite + Tailwind (dark theme)
- **Backend**: Python + Flask
- **PDF**: reportlab
- **JSONL**: stdlib `json`
- **No authentication, no database, no cloud storage**

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

## Tests

```bash
cd projects/vic/backend
python3 tests/test_pipeline.py   # full pipeline across Gemini + ChatGPT + Claude
python3 tests/test_http.py        # Flask endpoints via test client
python3 tests/test_crawler.py    # URL crawl + provider auto-detection
```

## Provider detection

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

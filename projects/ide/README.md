# Sovereign IDE

This folder contains the isolated Sovereign IDE clone, built as a separate workspace from the Sovereign Shards core.

## Launch

From `e:\dev shard\ide`:

```bash
python launch-ide.py
```

Or run:

```bash
python server.py
```

Then open http://127.0.0.1:8001 in your browser.

## Contents

- `server.py` — Python backend and REST API for IDE functionality
- `static/` — frontend assets (`index.html`, `app.js`, `style.css`)
- `launch-ide.py` — launcher script that starts the server and opens a browser
- `extensions.py` — extension loader and extension API support
- `extensions/` — extension files
- `workspace_state.json` — persisted workspace state
- `server_state.json` — persisted server state
- `README-IDE.md` — detailed user quick start guide
- `VSCODE_ARCHITECTURE.md` — architecture and implementation documentation
- `IMPLEMENTATION_COMPLETE.md` — feature completion summary

## Verification

This workspace has been validated:

- `python -m py_compile server.py extensions.py`
- `node -c static/app.js`

## Purpose

This folder is intentionally isolated from the `e:\dev shard` main project. It contains only the IDE clone and its support files.

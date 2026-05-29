# Sovereign IDE Build Plan

## Goal

Complete the standalone VS Code-style IDE clone in `ide/` with a solid, non-guessing implementation path.

## Current Status

- The IDE clone is isolated in `ide/`.
- Backend and frontend code are present and syntactically valid.
- Core feature set is implemented: file explorer, editor tabs, Monaco editor, sidebar views, Git status, search, command palette foundation, shell command runner, and extension listing.
- The `ide/` workspace is separate from the Sovereign Shards core.

## Verified

- `python -m py_compile server.py extensions.py`
- `node -c static/app.js`

## Remaining Build Work

### Phase 1: Stabilize Existing IDE

1. Confirm `server.py` serves:
   - `/` and `/index.html`
   - `/static/*`
   - `/api/fs/list`, `/api/fs/read`, `/api/fs/write`
   - `/api/workspace/state`
   - `/api/editor/*`
   - `/api/scm/status`
   - `/api/search`
   - `/api/fs/find`
   - `/api/extensions/list`
   - `/api/command`

2. Confirm frontend `/static/app.js` loads in browser and initializes Monaco.
3. Confirm file open/save flows work end-to-end.
4. Confirm command palette file search and command actions work.
5. Confirm explorer expand/collapse and tab switching work.

### Phase 2: Harden the Build

1. Add `ide/README.md` for standalone use.
2. Keep all IDE-specific assets inside `ide/`.
3. Avoid modifying any `e:\dev shard\app/` or `e:\dev shard\core/` files.
4. Document launch commands and supported features.

### Phase 3: Optional Extensions

1. Add terminal panel.
2. Add split editor groups.
3. Add a real command registry and command palette actions.
4. Add extension execution and UI.
5. Add more robust Git integration.

## Next Step

The current codebase in `ide/` is already a working build candidate.
The next step is to run the IDE and verify browser behavior, then implement any missing runtime features discovered during that verification.

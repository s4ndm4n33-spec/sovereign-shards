# V.I.C. — Code Audit & E2E Diagnostic

**Date**: 2026-06-25
**Scope**: `projects/vic/` and all subfolders
**Method**: Top-to-bottom source read of every backend module, frontend component, test file, and schema. Cross-referenced imports against definitions, API calls against implementations, and test expectations against actual code.

---

## Executive Summary

The V.I.C. project has a well-designed architecture and a clean separation of concerns. However, the codebase is in a **broken state** — no test can pass and the Flask backend cannot start. The root cause is a set of missing modules and a `KnowledgeGraph` class that was replaced with a stripped-down stub, breaking every consumer. There are **5 critical-severity issues** that must be fixed before any end-to-end flow works.

| Severity | Count |
|---|---|
| Critical (blocks all execution) | 5 |
| High (breaks specific features) | 4 |
| Medium (correctness/robustness) | 3 |
| Low (code quality/maintainability) | 4 |

---

## Critical Issues

### C1. Missing module: `deterministic_agent.py`

**Location**: `backend/vic/pipeline.py:33`
```python
from .deterministic_agent import DeterministicAgent
```

**Impact**: `pipeline.py` fails on import. Since `app.py` imports from `pipeline`, the entire Flask backend cannot start. Every test that imports `vic.app` or `vic.pipeline` also fails.

**Evidence**: `Glob` for `projects/vic/backend/vic/deterministic_agent.py` returns no matches. The module does not exist anywhere in the project.

**Fix**: Create `deterministic_agent.py` with a `DeterministicAgent` class that has a `process(self, raw: dict) -> dict` method. Based on usage at `pipeline.py:168` (`agent.process({"text": json.dumps(sessions)})`), it should return an IR dict. A minimal stub:
```python
class DeterministicAgent:
    def process(self, raw: dict) -> dict:
        return {"intents": []}
```

---

### C2. Missing functions: `result_to_dict` and `make_pdf_bytes`

**Location**: `backend/vic/pipeline.py` (end of file, line 184)
**Imported by**:
- `backend/vic/app.py:44` — `from .pipeline import ProcessResult, make_pdf_bytes, process_conversations, process_inputs, result_to_dict`
- `backend/tests/test_pipeline.py:22` — `from vic.pipeline import process_inputs, result_to_dict, make_pdf_bytes`

**Impact**: `app.py` cannot import, so the Flask app never starts. `test_pipeline.py` fails on import. `test_http.py` and `test_crawler.py` both import `vic.app`, so they fail too.

**Evidence**: `pipeline.py` defines `process_inputs`, `process_conversations`, and `ProcessResult`, but does NOT define `result_to_dict` or `make_pdf_bytes`. The file ends at line 184.

**Fix**: Add to `pipeline.py`:
```python
def result_to_dict(result: ProcessResult) -> dict:
    from dataclasses import asdict
    d = asdict(result)
    d["date_range"] = list(result.date_range)
    d["themes"] = [list(t) for t in result.themes]
    return d

def make_pdf_bytes(result: ProcessResult, title: str) -> bytes:
    # Convert ProcessResult.sessions back to Conversation list,
    # or refactor build_pdf to accept ProcessResult directly.
    from .output import build_pdf
    # build_pdf expects list[Conversation], but result has sessions (dicts).
    # This requires a reverse adapter or a new PDF builder.
    ...
```

Note: `output.py` has `build_pdf(conversations: list[Conversation], project_title: str)` but the signature is incompatible — `make_pdf_bytes` receives a `ProcessResult` (which has `sessions: list[dict]`, not `Conversation` objects). This is a design gap, not just a missing function.

---

### C3. `KnowledgeGraph` API mismatch — V2 backend completely broken

**Location**: `backend/vic/knowledge_graph.py`

**Current implementation** (stripped-down intent reducer):
```python
class KnowledgeGraph:
    def __init__(self, store=None):
        # store is intentionally ignored
        self.nodes: Dict[str, Dict] = {}
        self.edges: List[Dict] = []
    
    def apply(self, intents): ...
    def get_node(self, node_id): ...
    def get_edges(self): ...
```

**Expected by consumers**:
| Consumer | Call | Exists? |
|---|---|---|
| `app.py:360` | `KnowledgeGraph(_store(), repository_id=repo_id)` | No — `__init__` doesn't accept `repository_id` |
| `app.py:374` | `kg.neighbors(node_id)` | No |
| `app.py:375` | `kg.incoming(node_id)` | No |
| `app.py:376` | `kg.nodes.get(node_id, {})` | Partially — `nodes` is a dict but values are raw dicts, not enriched |
| `app.py:377` | `kg.to_dict()` | No |
| `app.py:411` | `kg.nodes.get(event_id)` | Same as above |
| `app.py:414` | `kg.incoming(event_id)` | No |
| `app.py:415` | `kg.neighbors(event_id)` | No |
| `biography.py:36` | `kg.store` | No — `store` is ignored in `__init__` |
| `evolution.py` | `kg.store`, `kg.nodes`, `kg.incoming()`, `kg.edges` (as Edge objects) | No |
| `test_historian_v2.py:142` | `KnowledgeGraph(store, repository_id=repo_id)` | No |
| `test_historian_v2.py:143-144` | `kg.nodes`, `kg.edges` (as Edge objects with `.confidence`, `.relationship_type`) | No — edges are plain dicts |
| `test_historian_v2.py:147` | `kg.edge_type_counts()` | No |
| `test_historian_v2.py:152` | `e.relationship_type == EdgeType.IMPLEMENTS.value` | No — edges are dicts, not Edge objects |

**Impact**: Every V2 endpoint (`/api/graph`, `/api/biography`, `/api/evolution`, `/api/provenance`) will raise `TypeError` or `AttributeError`. `test_historian_v2.py` fails immediately.

**Fix**: The `KnowledgeGraph` class needs a full rewrite to:
1. Accept `(store, repository_id)` in `__init__`
2. Build typed edges from store events/decisions using keyword inference
3. Store edges as `Edge` objects (from `graph_model.py`)
4. Implement `neighbors(node_id)`, `incoming(node_id)`, `to_dict()`, `edge_type_counts()`
5. Expose `store` attribute for `biography.py` and `evolution.py`

---

### C4. `biography.py` references `kg.store` — guaranteed `AttributeError`

**Location**: `backend/vic/biography.py:36`
```python
kg.store  # AttributeError: 'KnowledgeGraph' object has no attribute 'store'
```

**Impact**: `/api/biography` endpoint crashes. `test_historian_v2.py:167` fails.

**Fix**: Depends on C3 — once `KnowledgeGraph.__init__` stores `self.store = store`, this works.

---

### C5. `evolution.py` references nonexistent attributes and imports

**Location**: `backend/vic/evolution.py`

**Issues**:
- Calls `kg.store` — no such attribute (same as C4)
- Calls `kg.nodes` — exists but as `Dict[str, Dict]`, not enriched nodes
- Calls `kg.incoming(node_id)` — no such method
- Calls `kg.edges` — exists but as `List[Dict]`, not `List[Edge]`
- Imports `from .extract import _keywords` — `_keywords` does not exist in `extract.py`

**Impact**: `/api/evolution` endpoint crashes. `test_historian_v2.py:185+` fails.

**Fix**: Depends on C3. Also fix the `_keywords` import — either add it to `extract.py` or inline the keyword logic.

---

## High-Severity Issues

### H1. `app.py` imports `make_pdf_bytes` from `pipeline` but it doesn't exist

**Location**: `backend/vic/app.py:44`

This is the same as C2 but specifically affects the `/api/pdf` endpoint. Even if the import were fixed, `app.py:162` calls `make_pdf_bytes(result, title)` where `result` is a `ProcessResult` — but `output.py`'s `build_pdf` expects `list[Conversation]`. The PDF endpoint needs a bridge function or `build_pdf` needs to be refactored to accept `ProcessResult`.

---

### H2. `app.py` `/api/graph` endpoint constructs `KnowledgeGraph` with wrong signature

**Location**: `backend/vic/app.py:371`
```python
kg = KnowledgeGraph(_store(), repository_id=repo_id)
```

This passes 2 positional args + 1 kwarg, but `KnowledgeGraph.__init__(self, store=None)` only accepts 1. This raises `TypeError: __init__() got an unexpected keyword argument 'repository_id'`.

Same issue at lines 389, 399, 410.

---

### H3. `test_pipeline.py` imports `make_pdf_bytes` and `result_to_dict` — both missing

**Location**: `backend/tests/test_pipeline.py:22`

The test will fail on import with `ImportError: cannot import name 'result_to_dict'` (or `make_pdf_bytes`). This is the same root cause as C2.

---

### H4. `test_historian_v2.py` expects `KnowledgeGraph` with full V2 API

**Location**: `backend/tests/test_historian_v2.py:142-230`

The test expects:
- `kg.nodes` as a dict of enriched node objects (with `.get("title")`, `.get("occurred_at")`)
- `kg.edges` as a list of `Edge` objects (with `.confidence`, `.relationship_type`)
- `kg.edge_type_counts()` method
- `store.upsert_edge(edge)` and `store.list_edges(relationship_type=...)` — these DO exist in `store.py`

The test is well-written and correctly describes the intended V2 API. The implementation just doesn't match.

---

## Medium-Severity Issues

### M1. `temporal_query.py` `reconstruct_at_arc` has dead code

**Location**: `backend/vic/temporal_query.py:36-54`

The method iterates arcs and checks `if "ADD_NODE" in p` but never populates `snapshot_nodes` or `snapshot_edges` — both remain empty dicts/lists. The `continue` statement skips all processing. The method always returns empty results.

---

### M2. `narrative_engine.py` arc segmentation is naive

**Location**: `backend/vic/narrative_engine.py:89-103`

`_build_arcs` simply chunks every 5 events into an arc, regardless of temporal gaps, entity changes, or semantic boundaries. This produces arbitrary arcs with no narrative coherence.

---

### M3. `causal_graph.py` `_process_arc` accesses `arc.entities` but `NarrativeBlock.entities` is `List[str]`

**Location**: `backend/vic/causal_graph.py:37`

The method iterates `entities[i]` and `entities[i+1]` as consecutive pairs, treating consecutive entity mentions as causal transitions. This is a very weak causal signal — adjacency in a list does not imply causation.

---

## Low-Severity Issues

### L1. Duplicate API client: `api.ts` and `archive-api.ts` are identical

**Location**: `frontend/src/lib/api.ts` and `frontend/src/lib/archive-api.ts`

Both files contain the exact same code: `processFiles`, `crawlUrls`, `downloadPdf`, `downloadJsonl`, and `triggerDownload`. `history-api.ts:4` re-exports from `archive-api.ts`, but `App.tsx:14` imports from `api.ts`. One file should be deleted and the other should be the single source.

---

### L2. `pipeline.py` `_parse_files` falls through to Claude parser for unknown files

**Location**: `backend/vic/pipeline.py:85-87`

If a file doesn't match any provider heuristic, it tries `parse_claude_file` first, then `parse_chatgpt_file` if no Claude result. This silent fallback could misparse files and produce incorrect provider labels.

---

### L3. `store.py` `DEFAULT_DB_PATH` uses `Path.home()` which may not be writable

**Location**: `backend/vic/store.py:46`

In containerized or read-only environments, `~/.vic/historian.db` may fail. The `VIC_DB_PATH` env var override exists but isn't documented in the README.

---

### L4. `app.py` CORS headers are open (`*`) with a comment saying "local sovereign"

**Location**: `backend/vic/app.py:72`

`Access-Control-Allow-Origin: *` is set on all responses. While the design is local-only, this header would allow any website to call the local API if the user has the server running. For a sovereign tool, this should be restricted to `localhost` origins.

---

## E2E Diagnostic: Test-by-Test

### `test_pipeline.py` — FAILS on import
```
ImportError: cannot import name 'result_to_dict' from 'vic.pipeline'
```
**Root cause**: C2 (missing functions) + C1 (missing `deterministic_agent`)

### `test_http.py` — FAILS on import
```
ImportError: cannot import name 'make_pdf_bytes' from 'vic.pipeline'
(via `from vic.app import app` → `app.py` imports from `pipeline`)
```
**Root cause**: C2 + C1

### `test_crawler.py` — FAILS on import
```
ImportError: cannot import name 'make_pdf_bytes' from 'vic.pipeline'
(via `from vic.app import app`)
```
**Root cause**: C2 + C1

### `test_historian.py` — FAILS on import
```
ImportError: cannot import name 'make_pdf_bytes' from 'vic.pipeline'
(via `from vic.app import app` in test setup, or directly via pipeline imports)
```
**Root cause**: C2 + C1

### `test_historian_v2.py` — FAILS at runtime
```
TypeError: KnowledgeGraph.__init__() got an unexpected keyword argument 'repository_id'
```
**Root cause**: C3 (KnowledgeGraph API mismatch)

---

## Fix Priority Order

The issues have a dependency chain. Fixes must be applied in this order:

1. **C1**: Create `deterministic_agent.py` with `DeterministicAgent` class
2. **C2**: Add `result_to_dict` and `make_pdf_bytes` to `pipeline.py` (requires bridging `ProcessResult` → `build_pdf`)
3. **C3**: Rewrite `KnowledgeGraph` to accept `(store, repository_id)`, build typed edges, implement `neighbors`/`incoming`/`to_dict`/`edge_type_counts`
4. **C4 + C5**: Fix `biography.py` and `evolution.py` to use the new `KnowledgeGraph` API; fix `_keywords` import
5. **H1-H4**: Verify all endpoints and tests pass with the fixed imports

After steps 1-2, the V1 pipeline (`test_pipeline.py`, `test_http.py`, `test_crawler.py`, `test_historian.py`) should pass.
After steps 3-4, the V2 pipeline (`test_historian_v2.py`) should pass.

---

## Architecture Assessment

### Strengths
- **Clean separation**: detect → parse → extract → output pipeline is well-factored
- **Sovereignty by design**: stateless archive processing, local SQLite store, no cloud deps
- **Deterministic extraction**: keyword-based, no LLM dependency, reproducible
- **Typed graph model**: `Edge`, `EdgeType`, `Claim` dataclasses are well-designed
- **Provenance-first**: every claim has an evidence chain with event IDs
- **Test coverage**: tests exist for every major flow (archive, HTTP, crawler, historian V1+V2)
- **Frontend design**: dark sovereign aesthetic with thoughtful color system and micro-interactions

### Weaknesses
- **V2 knowledge graph is a stub**: the most advanced features (biography, evolution, provenance) are completely non-functional
- **Import chain fragility**: `pipeline.py` imports a missing module, which cascades to break the entire backend
- **No CI integration**: tests are standalone scripts (`if __name__ == "__main__"`), not pytest-compatible
- **Duplicate frontend API client**: `api.ts` and `archive-api.ts` are identical
- **Naive narrative segmentation**: 5-event chunks ignore temporal/semantic boundaries

---

## Summary

The V.I.C. project has a solid architectural foundation and a clear vision, but is currently in a non-functional state. The V1 archive pipeline (detect → parse → extract → PDF/JSONL) is architecturally complete but blocked by 2 missing pieces in `pipeline.py`. The V2 historian (knowledge graph, biography, evolution, provenance) is architecturally designed but the core `KnowledgeGraph` class was replaced with a stub that doesn't implement the API every consumer expects. Fixing the 5 critical issues in the listed order will restore full functionality.

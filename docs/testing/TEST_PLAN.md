# Sovereign Shards — Test Plan

> 127 tests · 13 files · 1,204 lines · stdlib `unittest` only · runs in ~1.5 s

---

## Quick Start

```bash
# From the project root
python -m unittest discover -s tests -v
```

No external test dependencies. Uses only `unittest` + `tempfile` + `json` + `os` from the standard library. The `conftest.py` module auto-mocks `psutil` if it isn't installed (CI-friendly).

---

## File Map

| File | Tests | Lines | What It Covers |
|------|------:|------:|----------------|
| `conftest.py` | — | 32 | Mocks `psutil` for environments where it's absent |
| `test_memory.py` | 17 | 184 | Tier 2 + 3 memory: remember, recall, forget, overwrite, size-cap prune, atomic write, working memory append/read/compress/reflect-trigger |
| `test_retriever.py` | 10 | 91 | BM25: tokenize, scoring, relevance ranking, top-k, edge cases (empty query, empty chunks), score ordering |
| `test_graph.py` | 9 | 106 | DAG task planner: topo-sort, parallel tiers, single step, empty graph, cycle detection, diamond deps, ready-steps, format |
| `test_planner.py` | 5 | 59 | Plan parsing: valid JSON, fenced markdown, garbage fallback, empty arrays, autonomy mode preservation |
| `test_executor.py` | 10 | 99 | Step prompt building, confirmation gating per autonomy mode (manual/auto-full/auto-safe/semi), tool execution, result formatting |
| `test_circuit_breaker.py` | 9 | 89 | Repeat-call trip, varied-call no-trip, repeat-error trip, step/turn limits, reset, stats, force-skip escalation, recovery prompt format |
| `test_context.py` | 8 | 62 | Token estimation (basic, longer, empty), context trimming (under budget, middle trim, system kept, empty), summary compression marker |
| `test_contracts.py` | 6 | 38 | Frozen dataclasses: AgentStep, ToolCall, ToolResult, AgentTask — defaults, immutability |
| `test_sandbox.py` | 5 | 112 | Syntax check, AST import parse, conflict marker detection, full 5-check gauntlet, report summary |
| `test_forge.py` | 17 | 251 | Inference forge: intent detection (explicit/create/existing/no-match), research prompt, research parse (valid/fenced/garbage), slugify, forge prompt, code assembly, fence stripping, validation (valid/syntax-error/missing-run/missing-name), test-arg generation, JSONL logging |
| `test_registry.py` | 9 | 101 | Tool registry: builtin registration, script tool discovery, unknown-tool error, describe output, side-effect classification, read_file execution, list_dir execution, script tool run, timeout handling |
| `test_reflection.py` | 5 | 57 | Reflection: prompt building (entry count, content), parse (valid JSON, fenced, garbage, missing fields, optional fields) |
| **Total** | **127** | **1,204** | |

---

## What Each Module Tests

### `test_memory.py` — Tier 2 + 3 Memory System
The memory system is the backbone of J's cross-session intelligence. Tests cover:
- **Long-term (Tier 3):** `remember(key, value)` → `recall(key)` round-trip, missing-key handling, `forget()`, `recall_all()`, key overwrite, size-cap auto-prune (oldest entries evicted when cap exceeded), atomic file writes (temp file → rename)
- **Working (Tier 2):** `append()` → `read()`, `read_recent(n)` slicing, empty-read safety, `needs_reflection()` weight trigger, `replace_entries()` for post-reflection compaction, `compress_turn()` step→result→issue compression, `format_for_context()` string output, empty-format guard

### `test_retriever.py` — BM25 Retrieval Engine
J finds relevant memory chunks without embeddings or a vector DB. Tests cover:
- Tokenisation: lowercase splitting, underscore handling, mixed alphanumeric
- BM25 scoring: non-zero on match, zero on no-match
- End-to-end retrieval: relevance ranking (most relevant chunk first), `top_k` limiting, empty-query and empty-chunk edge cases, score presence + descending order

### `test_graph.py` — DAG Task Planner
J decomposes goals into dependency-aware step graphs. Tests cover:
- Topological sort producing correct parallel tiers (A→B→C = 3 tiers, A+B→C = 2 tiers)
- Single-step and empty-graph edge cases
- Cycle detection raises `ValueError`
- Diamond dependency (A→B, A→C, B→D, C→D) resolves correctly
- `ready_steps()` returns only steps whose deps are satisfied
- `format_graph()` output string structure

### `test_planner.py` — Plan Parsing
The planner converts model output into executable step lists. Tests cover:
- Valid JSON array parsing
- JSON wrapped in markdown code fences (` ```json ... ``` `)
- Garbage/unparseable input falls back to single "execute" step
- Empty JSON array handling
- Autonomy mode preserved through the parse pipeline

### `test_executor.py` — Step Execution & Confirmation Gating
The executor runs each step with appropriate safety gates. Tests cover:
- Step prompt contains step ID, description, and tool names
- **Confirmation modes:**
  - `manual` — always requires confirmation
  - `auto-full` — never requires confirmation
  - `auto-safe` — blocks exec/bash, allows read-only tools
  - `semi` — blocks write tools, allows read tools
- Tool execution success and error paths
- Result formatting (OK vs error output)

### `test_circuit_breaker.py` — Self-Healing Loop Detection
Prevents J from burning tokens on stuck loops. Tests cover:
- Healthy initial state
- Repeat identical calls trip the breaker
- Varied calls do not trip
- Repeated errors trip the breaker
- Step/turn limits trigger escalation
- `reset_step()` clears state for new step
- `stats()` output format
- Force-skip after multiple consecutive trips
- Recovery prompt contains useful guidance

### `test_context.py` — Token Budget & Context Trimming
Keeps J's context window within model limits. Tests cover:
- Token estimation: basic strings, longer content, empty string
- Under-budget context passes through unchanged
- Over-budget context trims middle messages, keeps system + recent
- System message always preserved regardless of budget
- Empty message list safety
- Compressed summary contains `[compressed]` marker when active

### `test_contracts.py` — Data Contracts
Core data structures used across the agent. Tests cover:
- `AgentStep` is frozen (immutable after creation)
- `AgentStep.depends_on` defaults to empty tuple
- `ToolCall.args` defaults to empty dict
- `ToolResult.ok` and `.error` factory methods
- `AgentTask` defaults (mode, max_steps)

### `test_sandbox.py` — Pre-Push Validation
Catches broken code before it leaves the drive. Tests cover:
- Syntax check passes clean files, catches `SyntaxError`
- AST import parse on valid Python
- Unparseable file handled gracefully
- Conflict marker detection (`<<<<<<<`, `>>>>>>>`)
- Full 5-check gauntlet on a clean mini-project
- Report summary format

### `test_forge.py` — Inference Tool Forge
J builds new tools at runtime from plain-English requests. Tests cover:
- **Intent detection:** explicit "build a tool" triggers, "create" keyword triggers, existing-tool-name mentions return false, no-match heuristic returns false
- **Research prompt:** contains user request, includes local BM25 hits when provided
- **Research parse:** valid JSON, JSON inside markdown fences, garbage fallback
- **Slugify:** basic strings, special characters, empty input
- **Forge prompt:** contains spec details (tool name, description, parameters)
- **Code assembly:** wraps implementation in template, strips markdown fences
- **Validation:** valid tool passes, syntax error fails, missing `run()` fails, missing `TOOL_NAME` fails
- **Test-arg generation:** int, path, and string argument types produce sensible defaults
- **JSONL logging:** creates/appends forge event log

### `test_registry.py` — Tool Registry & Discovery
J's tool system auto-discovers tools from `tools/run/`. Tests cover:
- Built-in tools (`read_file`, `list_dir`) registered at init
- Script tools discovered from filesystem
- Unknown tool returns error, doesn't crash
- `describe()` output includes all registered tools with descriptions
- Side-effect classification (read vs write)
- `read_file` and `list_dir` execution against real temp files
- Script tool subprocess execution
- Timeout handling on slow tools

### `test_reflection.py` — Weight-Triggered Reflection
J prunes its own memory when summaries get heavy. Tests cover:
- Reflection prompt includes entry count and actual entries
- Valid JSON parse of reflected output
- Markdown-fenced JSON stripped correctly
- Garbage input returns empty result
- Missing required fields handled gracefully
- Optional fields (pruned keys, insights) captured when present

---

## Design Decisions

1. **Zero test dependencies.** Tests use only `unittest`. No pytest, no mock libraries, no test runners to install. Matches the project's "2 deps" philosophy.

2. **`conftest.py` psutil mock.** The app's `__init__.py` imports `system_tools` which imports `psutil`. Rather than making psutil a hard test dep, `conftest.py` injects a stub module before any app imports happen. This means tests run in CI, in containers, and on bare installs.

3. **Temp directories everywhere.** Every test that touches the filesystem creates a `tempfile.TemporaryDirectory` and cleans up after itself. No test state bleeds between runs.

4. **Fast.** The full suite runs in ~1.5 seconds. No network calls, no model inference, no disk I/O beyond temp files. Fast enough to run on every change.

5. **Mirrors the architecture.** One test file per module. If a module exists in `app/agent/`, it has a corresponding `tests/test_*.py`. Makes it obvious what's tested and what isn't.

---

## Running Individual Modules

```bash
# Run a single module
python -m unittest tests.test_memory -v

# Run a single test class
python -m unittest tests.test_forge.TestValidateTool -v

# Run a single test
python -m unittest tests.test_graph.TestTopoTiers.test_diamond -v
```

---

## Adding New Tests

1. Create `tests/test_<module>.py`
2. Import the module under test from `app.agent.<module>`
3. Subclass `unittest.TestCase`
4. Name methods `test_<what_it_checks>`
5. Use `tempfile.TemporaryDirectory()` for any file ops
6. Run: `python -m unittest discover -s tests -v`

---

*127 tests. 1.5 seconds. Zero cloud calls. Sovereign.*

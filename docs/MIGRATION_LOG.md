# SOVEREIGN SHARDS — MIGRATION LOG

> For the next agent, developer, or collaborator picking up this project.
> Read this entire document before writing a single line of code.

**Last updated:** 2026-05-14 (Session 30)
**Current agent:** Viktor (getviktor.com) — PRs #16–#43. 198 total commits on main.
**Repo:** github.com/s4ndm4n33-spec/sovereign-shards
**Branch:** `main` (active development branch).

---

## 0. AUDIT NOTE (2026-05-10)

This log was reconciled against the current repository state on **May 10, 2026**.

Verified updates:
- Active branch confirmed as `main`. No `work` branch exists in the remote.
- `app/chat.py` line-count annotation updated (937 lines).
- Architecture tree updated: added `script_tool.py`, `tool_router.py`, `tool_schema.py`, `setup.bat`, `INSTALL.md`, `LANGUAGE_DIAGNOSTIC.md`.
- Model reference updated from 14B/3-shard to 7B/2-shard (swap completed in Session 17).
- System prompt annotation updated (~809 chars, ~158 tokens — rewritten in Session 17).
- Known bugs section updated: 5 of 9 issues resolved or partially resolved.
- `.env.example` is now current (7B/2048/256 defaults).
- Commit history updated (65 total commits including PRs #12–#15 and tool layer rebuild).
- File counts updated (99 files, 69 Python modules).
- `docs/MIGRATION_LOG.json` refreshed with M7 milestone and branch correction.
- Test-suite summary wording updated to reflect current `tests/` layout.



## 0.1 TOOL LAYER REBUILD NOTE (2026-05-10)

A full tool-layer rebuild landed on **May 10, 2026** to make the registry deterministic, dict-compatible, schema-aware, side-effect-aware, and router-compatible for both modern and legacy execution paths.

Delivered components:
- `app/agent/tool_schema.py`: canonical `ToolSpec`, spec normalisation, and strict argument validation (required/type/unknown checks).
- `app/agent/script_tool.py`: subprocess wrapper for `tools/run/*.py` with timeout control, stdin support, merged stdout/stderr, and structured `{"ok": ...}` responses.
- `app/agent/tool_router.py`: `route_tool_call()` with existence checks, schema validation, side-effect enforcement, safe execution, and non-crashing structured returns.
- `app/agent/tool_registry.py`: dict-like registry API (`__getitem__`, `get`, `__contains__`, `keys`), deterministic `as_prompt_block()`, restrictions gate, script auto-discovery, and legacy `execute(tool_name, tool_args)` JSON shim.

Operational impact:
- Fixes the legacy `.get()` crash class by exposing dictionary semantics directly on registry objects.
- Unifies tool-call validation across router and compatibility paths.
- Introduces explicit side-effect restrictions (`read/write/exec/network`) for sovereign-safe default operation.
- Preserves llama.cpp-era positional tool invocation while producing deterministic stringified JSON outputs.

## 1. WHAT THIS IS

A fully local, USB-portable developer agent called **J** (sometimes **B.L.U.E.-J**). It runs on a 16GB RAM Windows machine from a FAT32-formatted Kingston 2.0 USB drive. No cloud. No API keys. No host dependencies. The model, the server, the tools, the runtime — everything lives on the shard.

J is not a chatbot. J is an executor. Given a task, J decomposes it, calls tools, verifies results, and iterates. The language model is the language engine. The framework is the reasoning layer.

The project is backed by a 31-page thesis: `sovereign_intelligence_thesis.pdf` — a philosophical and technical framework for sovereign AI systems that persist on consumer hardware.

---

## 2. THE OWNER

**Mike McCollum** (@s4ndm4n33-spec / @vikvondoom2026)

Key preferences:
- Conservative token usage. Copy-paste over rewrites. Don't waste credits.
- British English for voice modules when integrated.
- Sardonic, JARVIS-like personality for J. Never sycophantic.
- Local-first. Every decision must respect the hardware.
- The Five Masters are the brand. Non-negotiable.
- Ask before pushing. Always.

---

## 3. HARDWARE CONSTRAINTS (Hard Rules — Do Not Violate)

| Constraint | Value | Why |
|---|---|---|
| Total RAM | 16 GB | System ceiling. Model + OS + server must fit. |
| Context window | **2048 tokens** | 4096 redlines the system. Owner tested, owner decided. Do not raise. |
| GPU | Intel HD Graphics 530 | Integrated. 1 GB shared VRAM. Not worth offloading. `GPU_DEVICE=none`. |
| USB format | FAT32 | 4 GB max file size. All model files must be split below 4 GB. |
| USB interface | USB 2.0 | ~30 MB/s read. Boot is slow. Optimise for minimal disk reads. |
| Python | Embedded on USB | `E:\dev shard\python\python.exe`. Never call host Python. |
| Dependencies | 2 only | `python-dotenv` + `psutil`. No new pip packages without extremely good reason. |

### What 2048 Context Means

At 2048 tokens with 256 reserved for generation, the working budget is **1792 tokens**.

The system prompt (J-system.txt) is currently ~158 tokens (~809 chars, rewritten in Session 17). That leaves ~1634 tokens for the entire conversation — system prompt + user messages + assistant messages + memory injection + tool results.

**Implications:**
- System prompt must NEVER exceed ~400 tokens. Every word must earn its place.
- Tool results get truncated by `preflight_trim` if they're too long.
- Working memory injection must be surgical — BM25 retrieval picks only relevant entries.
- Multi-turn conversations compress aggressively. Expect 5–8 effective turns before context pressure forces trimming.
- The model (7B) has limited instruction-following at this context size. Keep instructions short and direct.

---

## 4. ARCHITECTURE

```
sovereign-shards/
├── run.py                      # Entry point. Parses args, calls run_chat().
├── run-shard.bat               # Windows one-click launcher. Calls shard Python.
├── setup.bat                   # One-click first-time installer (downloads Python, llama.cpp, model).
├── start-server.bat            # Manual server start (if not using run.py auto-start).
├── run-llama.bat               # Direct CLI mode (bypasses framework).
├── INSTALL.md                  # Quick install guide for setup.bat and manual setup.
├── .env                        # Local config (gitignored). See .env.example.
│
├── app/
│   ├── chat.py                 # Main chat loop (~992 lines). Heart of the system.
│   ├── client.py               # RuntimeConfig — reads .env, builds config dataclass.
│   ├── local_server.py         # Launches llama.cpp server with hardware-aware flags.
│   ├── router.py               # Fast deterministic command router (zero inference cost).
│   ├── file_tools.py           # read_file, write_file, list_dir (FAT32-safe).
│   ├── system_tools.py         # get_system_snapshot (RAM, CPU, disk).
│   ├── session.py              # SessionLogger — transcript logging.
│   ├── runtime_log.py          # RuntimeJsonLogger — structured event log.
│   ├── errors.py               # Custom exceptions.
│   ├── doctor.py               # Preflight diagnostics (run.py --doctor).
│   │
│   └── agent/
│       ├── context.py           # Context budget: trim_context, preflight_trim, reconstruct_context.
│       ├── working_memory.py    # Tier 2: append-only JSONL of step summaries.
│       ├── memory.py            # Tier 3: long-term memory (persistent key-value store).
│       ├── retriever.py         # BM25 retrieval over memory entries.
│       ├── reflection.py        # Weight-triggered memory compression (LLM-assisted).
│       ├── planner.py           # Task decomposition: goal → sub-steps with success criteria.
│       ├── executor.py          # Step execution with verification.
│       ├── verifier.py          # Output verification against success criteria.
│       ├── graph.py             # Task graph: parallel-safe dependency resolution.
│       ├── parallel.py          # ThreadPoolExecutor for independent sub-tasks.
│       ├── tool_schema.py       # Canonical ToolSpec dataclass, spec normalisation, strict arg validation.
│       ├── tool_registry.py     # Dict-like tool registry: schema-aware, side-effect gated, prompt block gen.
│       ├── tool_router.py       # route_tool_call(): validate → enforce policy → execute → structured return.
│       ├── script_tool.py       # ScriptTool: subprocess wrapper for tools/run/*.py with timeout + stdin.
│       ├── tool_forge.py        # Generate new tools from natural language descriptions.
│       ├── tool_researcher.py   # Research step before forging (web-free, pattern-based).
│       ├── tool_template.py     # Template for generated tools.
│       ├── circuit_breaker.py   # Detect infinite tool loops and force recovery.
│       ├── sandbox.py           # Pre-push validation: syntax, imports, tests, Five Masters.
│       ├── optimizer.py         # Five Masters code optimizer (5-stage pipeline).
│       ├── transforms.py        # 8 deterministic AST transforms across all 5 Masters.
│       ├── refactor.py          # Cross-file AST analysis (dead code, circular imports).
│       ├── indexer.py           # Project directory indexer for code search.
│       ├── streaming.py         # Streaming response handling.
│       ├── visual.py            # HTML report generation.
│       ├── contracts.py         # Pre/post condition decorators.
│       └── task_store.py        # Persistent task state.
│
├── core/
│   ├── fivemasters.py          # Five Masters AST-based code governance (13K chars).
│   └── persona_dev.json        # J persona definition.
│
├── prompts/
│   ├── J-system.txt            # System prompt (~809 chars, ~158 tokens). KEEP IT LEAN.
│   └── J-chat-template.jinja   # ChatML Jinja template for llama.cpp server.
│
├── tools/run/                  # Script-based tools (auto-discovered by registry).
│   ├── bash.py, exec.py        # Shell execution.
│   ├── read.py, write.py       # File I/O.
│   ├── search.py, tree.py      # Code search and directory listing.
│   ├── git.py                  # Git operations.
│   ├── test.py                 # Test runner.
│   ├── integrity.py            # File integrity checking.
│   ├── scaffold.py             # Project scaffolding.
│   ├── sql.py                  # SQLite queries.
│   ├── str_replace.py          # String replacement in files.
│   └── registry.json           # Tool metadata manifest.
│
├── tests/                      # 14 test files + shared fixtures (all passing in sandbox at last run).
│
├── docs/
│   ├── USER_MANUAL.md          # User-facing documentation.
│   ├── BUSINESS_MODEL.md       # Three-tier business model.
│   ├── TEST_PLAN.md            # Test strategy and coverage.
│   ├── CODE_OPTIMIZER_SPEC.md  # Five Masters optimizer technical spec.
│   ├── APPENDIX_E.md           # Implementation record (thesis appendix).
│   ├── FINAL_PUSH_NOTES.md     # Build notes from initial sprint.
│   ├── LANGUAGE_DIAGNOSTIC.md  # Language drift diagnostic notes.
│   ├── MIGRATION_LOG.json      # Structured migration log (milestones M1–M7).
│   └── landing.html            # Product landing page.
│
├── models/                     # GGUF model files (gitignored, on USB only).
│   └── J-00001-of-00002.gguf  # Qwen2.5-Coder-7B-Instruct Q4_K_M (2 shards). SWAP DONE.
│
├── model-server/               # llama.cpp binaries (gitignored, on USB only).
│   └── server.exe              # llama-server. MUST be Vulkan build for GPU offload.
│
├── memory/                     # Runtime memory (gitignored).
│   ├── working_memory.jsonl    # Tier 2: rolling step summaries.
│   └── long_term.json          # Tier 3: persistent facts.
│
├── logs/                       # Runtime logs (gitignored).
│   ├── server/                 # llama.cpp server logs (one per session).
│   └── sessions/               # Chat transcripts.
│
└── assets/
    └── icon.png                # Sovereign Shard icon.
```

---

## 5. DATA FLOW

```
User Input
    │
    ▼
┌──────────────┐     handled=True     ┌──────────────┐
│  Fast Router  │ ──────────────────▶  │  Tool Exec   │ ──▶ Display result
│  (router.py)  │                      │  (registry)  │
└──────┬───────┘                      └──────────────┘
       │ handled=False
       ▼
┌──────────────────────────────────────┐
│  Context Reconstruction              │
│  1. Take system prompt (J-system.txt)│
│  2. BM25-retrieve working memory     │
│  3. BM25-retrieve long-term memory   │
│  4. Merge into system message        │
│  5. Trim to fit 2048-token budget    │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│  Pre-flight Budget Gate              │
│  3-stage escalation trim:            │
│    1. Summarise middle messages      │
│    2. Cap all messages, fewer tails  │
│    3. Hard truncate system to 60%    │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│  llama.cpp /v1/chat/completions      │
│  Streaming response via HTTP         │
│  Jinja ChatML template applied       │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│  ACTION Extraction + Budget Loop     │
│  If response contains ACTION:{...}   │
│  → parse tool name + args            │
│  → execute via registry              │
│  → inject result + budget counter    │
│  → break when budget exhausted       │
│  Budget set by router classification │
│  Hard ceiling: MAX_TOOL_HOPS=5       │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│  Working Memory Compression          │
│  Compress turn → one-line summary    │
│  Append to working_memory.jsonl      │
│  If >32KB → auto-reflection trigger  │
└──────────────────────────────────────┘
```

---

## 6. THE FIVE MASTERS

This is the engineering philosophy that governs all code quality decisions. It is the brand. It is non-negotiable.

| Master | Domain | What They Enforce |
|---|---|---|
| **Korotkevich** | Efficiency | No `for i in range(len(x))`. No `list(filter(...))`. No repeated dict lookups in loops. Prefer generators over materialised lists. |
| **Torvalds** | Error Handling | No bare `except:`. No `except Exception`. No `pass` in except blocks. Every exception must be handled with intent. |
| **Carmack** | Performance | No nested loops beyond O(n²). No string concatenation in loops. Flag excessive function nesting (>4 levels). |
| **Hamilton** | Fault Tolerance | Every function over 5 lines must have a return path for failure. Defensive coding. No silent failures. |
| **Ritchie** | Clarity | Functions use `snake_case`. Classes use `PascalCase`. All call sites updated when renaming. Dunders, privates, and `ALL_CAPS` are exempt. |

**Implementation:**
- Detection: `core/fivemasters.py` — pure AST analysis, zero inference cost.
- Transforms: `app/agent/transforms.py` — 8 deterministic AST transforms (one or more per Master).
- Pipeline: `app/agent/optimizer.py` — 5-stage: Input → Analysis → Plan → Transform → Verify.
- Command: `/optimize [path] [--dry-run] [--no-model] [--diff]`

The optimizer is the first product feature. It is designed to eventually refactor entire codebases. See `docs/CODE_OPTIMIZER_SPEC.md` for the full technical specification.

---

## 7. IDENTITY SYSTEM

J's identity is maintained through 4 layers:

1. **J-system.txt** — Loaded at startup into the system message. Contains voice, behaviour rules, tool format, and Identity Lock.

2. **Identity Lock** — The last lines of J-system.txt: "IDENTITY LOCK: You are J. You already agreed to this. Every response is from J, in English." Placed at the end for maximum recency salience in transformer attention.

3. **Context Reconstruction** — Every turn, `reconstruct_context()` rebuilds the messages from scratch. The system message (with identity) is always preserved. Memory is merged INTO the system message, never as a separate message that could push identity out.

4. **Jinja Chat Template** — `J-chat-template.jinja` forces the generation prefix `J: ` via `add_generation_prompt`. The model starts every response in J's voice.

**Known weakness:** At 2048 context, after ~10-15 turns of tool-heavy conversation, context pressure forces aggressive trimming. The system prompt survives (it's protected), but the model may lose coherence with so little conversation history. The Identity Lock mitigates this but doesn't eliminate it entirely.

**Qwen-specific issue:** Qwen2.5 models are bilingual (Chinese/English). Without explicit "Always respond in English" in the system prompt, the model may default to Chinese for short responses. This instruction is now baked into J-system.txt.

---

## 8. MEMORY ARCHITECTURE

### Tier 1: Active Context (what the model sees right now)
- The messages array sent to the LLM.
- Rebuilt every turn by `reconstruct_context()`.
- Budget-gated by `preflight_trim()`.

### Tier 2: Working Memory (rolling summaries)
- File: `memory/working_memory.jsonl`
- Append-only JSONL. Each entry: `{ts, step, result, issue?, decision?}`
- Compressed each turn from the full conversation into a one-line summary.
- When file exceeds 32KB, auto-reflection fires (LLM compresses N entries → ~5).
- Survives across sessions.

### Tier 3: Long-Term Memory (persistent facts)
- File: `memory/long_term.json`
- Key-value store. Persists learned facts, user preferences, tool discoveries.
- Never auto-pruned. Grows over the lifetime of the shard.
- Retrieved via BM25 — only relevant entries injected into active context.

### Retrieval
- `app/agent/retriever.py` implements BM25 (Okapi BM25) over memory entries.
- Given a task hint (the user's current message), it scores all memory entries and returns the top-K most relevant.
- Working memory: top 8 entries.
- Long-term memory: top 5 entries.

---

## 9. KNOWN BUGS AND OPEN ISSUES

### Resolved (Session 17 — 2026-05-08)
1. ~~**Chinese response on first turn.**~~ *FIXED.* Root cause was corrupted 3-shard GGUF split degrading attention layers, not prompting. Resplit to 2 clean shards from intact GGUF. See Session 17 for full diagnosis.
2. ~~**14B model still on USB.**~~ *FIXED.* Swapped to Qwen2.5-Coder-7B-Instruct Q4_K_M, split to 2 FAT32-safe shards.
4. ~~**`num_predict` may be wrong in user's .env.**~~ *FIXED.* `.env.example` now correctly defaults to `OLLAMA_NUM_PREDICT=256`.
6. ~~**`.env.example` is outdated.**~~ *FIXED.* Now reflects 7B model, 2048 context, 256 predict, `GPU_DEVICE=none`, and all current settings.

### Resolved (Session 18 — 2026-05-10)
11. ~~**Tool execution untested on real hardware.**~~ *FIXED.* Full 5-level graduated smoke test passed on live USB hardware (see Session 18 below). `run_bash`, `run_read`, `run_write`, `run_search` all validated end-to-end.
12. ~~**`_format_hardware_context()` is dead code.**~~ *FIXED.* Removed in PR #17.
13. ~~**`exec` side-effect blocked for `run_bash`.**~~ *FIXED.* PR #19 — `registry.restrictions["exec"] = True` after init.
14. ~~**`run_bash` stdin mapping broken.**~~ *FIXED.* PR #20 — arg name `"command"` → `"stdin"` in registry.json.
15. ~~**`run_bash` Windows threading race condition.**~~ *FIXED.* PR #21 — replaced Popen+daemon thread with `subprocess.run(capture_output=True)`.
16. ~~**Windows cp1252 encoding crashes.**~~ *FIXED.* PRs #22, #28 — `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` in `read.py`, `search.py`, and `script_tool.py`.
17. ~~**`working_memory.append()` signature mismatch.**~~ *FIXED.* PR #18 — `append(step_summary)` → `append(outcome.step.id, step_summary)`.
18. ~~**`run_search` arg reversal by J.**~~ *FIXED.* PR #26 + #28 — Hamilton fault tolerance: auto-detect reversed args using `os.path.isfile()` heuristic.
19. ~~**J post-answer runaway.**~~ *FIXED.* PRs #28–#32 — router-driven tool budget + post-gen trim + loop break on budget exhaustion + expanded stop tokens.
20. ~~**`BUILD_INFO.json` stale paths.**~~ *FIXED.* PR #17 — absolute paths → relative paths, added model_info section.

### Resolved (Session 19 — 2026-05-10)
24. ~~**Router only matched `run_*` tool prefixes.**~~ *FIXED.* `write_file`, `read_file`, `list_dir`, `system_snapshot` were invisible to the router because `_TOOL_PREFIX_RE` was `^(run_\w+)`. Extended to match ALL registered tool names. J overwrote `run.py` during endurance v1 because `write_file` fell through to the LLM.
25. ~~**Router had no Windows shell commands.**~~ *FIXED.* `_SHELL_PREFIXES` was Linux-only (`ls`, `cat`, `rm`). Added `dir`, `del`, `type`, `copy`, `move`, `md`, `rd`, `cls`, `ver`. Added `_BARE_SHELL` set for args-optional commands (`pwd`, `dir`, `cls`, `ver`).
26. ~~**`list_dir` with no args → "missing required argument: path".**~~ *FIXED.* Router defaults to `"."` when `list_dir` is called with no args.
27. ~~**Short correct answers forced unnecessary retries.**~~ *FIXED.* Budget=0 answer detection had a 20-char minimum length check. Math answers like `"2048."` (5 chars) were rejected and forced tool calls. Dropped length check for budget=0 — any non-empty answer accepted.
28. ~~**Router-handled turns invisible to J.**~~ *FIXED.* Router turns were not in J's message history. When asked "what file did I create?", J couldn't recall. Now injects one-line breadcrumbs after each router dispatch: `[SYSTEM] write_file test.txt: [OK] Wrote 10 bytes`.
29. ~~**J hallucinated "Five Masters" as mystical titles.**~~ *FIXED.* Added PROJECT FACTS block to J-system.txt: Five Masters = AST-based code governance, project = Python on Windows, explicit "you are NOT Qwen, you are J", "Never output Chinese or non-English text".
30. ~~**"Understood" stub detection too aggressive.**~~ *FIXED.* Simplified to exact match on `"understood"` / `"understood."` only. Long replies starting with "Understood, I will..." are now accepted.

### Still Open — Important (Blocks v1.0.1)
9. **`working_memory.replace_entries()` has a bug:** writes to `.tmp` file but never renames it to the real path. Atomic replace is broken — the old file persists. Fix is four lines (`os.replace`).
10. **`OLLAMA_NUM_PREDICT=256` limits agent tasks.** Tool-heavy `/plan` tasks need 512+ tokens to complete ACTION JSON without truncation. Current hardware is at 93.9% RAM at idle. Validate on dedicated hardware before raising.

### Resolved (Session 19 — Post-Gate Nit Fixes)
31. ~~**`run_bash`/`run_exec` arg splitting broke multi-word commands.**~~ *FIXED.* `run_bash python -c "print(2+2)"` was shlex-split into 3 args; only `"python"` piped to stdin → empty output. `run_bash del test.txt` → only `"del"` piped → syntax error. Fix: stdin-tools (`run_bash`, `run_exec`) now pass entire rest-of-line as single arg.
32. ~~**`run_read` backslash paths eaten by shlex.**~~ *FIXED.* `shlex.split()` treated `\J` in `prompts\J-system.txt` as escape → `promptsJ-system.txt`. Fix: `_split_args` normalises `\` → `/` before splitting. Python `open()` handles forward slashes on Windows.

### Still Open — Medium
33. **`run_search` multi-word patterns require quoting.** `run_search def main` splits as pattern=`"def"`, path=`"main"`. User must quote: `run_search "def main"`. This is documented behaviour — shlex splitting is correct.

### Still Open — Minor
21. **`ProjectManifest.txt` (~178KB)** is from the initial build (2026-04-24). Contains stale content. Low priority but should be updated or removed.
7. **`MIGRATION_LOG.json`** is maintained as a structured companion to this file (milestones M1–M14). Machine-readable migration record.
22. **Circuit breaker doesn't force-stop loops.** J sometimes ignores circuit breaker warnings and repeats identical tool calls. At 7B/2048 the model can't reliably process the recovery prompt. Tool budget mitigates this but doesn't fully replace circuit breaker enforcement.
23. **J identity confusion at context saturation.** Qwen 7B occasionally appends "I apologize..." or "As per my programming..." disclaimers after answering. Stop tokens now catch the most common patterns but new variants may surface.

---

## 10. STANDARDS AND CONVENTIONS

### Code Style
- Python 3.10+ (f-strings, `match` statements OK, `|` union types OK).
- `from __future__ import annotations` at the top of every module.
- Type hints on all function signatures.
- Docstrings on all public functions (Google style).
- No classes where a function will do. Dataclasses over regular classes.
- `pathlib.Path` over `os.path` everywhere.

### Naming
- Files: `snake_case.py`
- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `ALL_CAPS`
- Private: `_leading_underscore`

### Testing
- Framework: `unittest` (stdlib only — no pytest dependency).
- Test files: `tests/test_{module}.py`
- Run: `python -m pytest tests/ -v` (pytest works as a runner, but tests use unittest API).
- Current: 147+ tests, all passing in sandbox.
- Rule: no commit without passing tests. The sandbox validates before push.

### Git
- Single branch: `main`.
- Commit messages: `type: short description` (e.g., `fix: slim system prompt for 2048 budget`).
- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
- Always check with owner before pushing. They review before merge.

### Dependencies
- **Allowed:** `python-dotenv`, `psutil` (both already in `requirements.txt`).
- **Everything else:** stdlib only. This is a hard constraint.
- If you genuinely need a new dependency, justify it in writing and get owner approval.

---

## 11. CONFIGURATION REFERENCE

The `.env` file (gitignored) controls all runtime behaviour. Here are the critical settings for the current hardware:

```env
# CRITICAL — do not change without understanding implications
RUNTIME_BACKEND=llama_cpp
OLLAMA_NUM_CTX=2048              # HARD CEILING. Do not raise.
OLLAMA_NUM_PREDICT=256           # Generation budget. 256 at 2048 context.
GPU_DEVICE=none                  # Intel HD 530 — not worth offloading.
GPU_LAYERS=0                     # No GPU offload.
LLAMA_BATCH_SIZE=256             # Lower = less peak RAM.
OLLAMA_NUM_THREAD=2              # Match available cores. Don't over-thread.

# Tool budget (Session 18)
J_TOOL_BUDGET=3                  # Default per-turn tool calls. Router overrides per-prompt.

# LLM behaviour (Session 18)
LLAMA_REPEAT_PENALTY=1.3         # Reduces token-level repetition and Chinese drift.
LLAMA_STOP_TOKENS=<|im_end|>,<|im_start|>,\nYou:,\nUnderstood,\nI apologize,\nAs per my programming,\nI am not capable

# Server
LLAMA_HOST=127.0.0.1
LLAMA_PORT=8080
LLAMA_STARTUP_TIMEOUT=300        # 5 min for USB 2.0 model load.
LLAMA_SERVER_BINARY=model-server\server.exe
LLAMA_CLI_BINARY=model-server\llama.exe

# Model (7B, 2 FAT32-safe shards — swap complete)
LLAMA_MODEL_ALIAS=J
LLAMA_MODEL_PATH=models\J-00001-of-00002.gguf

# Template — do not change
LLAMA_CHAT_TEMPLATE=chatml
LLAMA_CHAT_TEMPLATE_FILE=prompts\J-chat-template.jinja
LLAMA_CHAT_TEMPLATE_KWARGS=       # MUST be empty or absent.

# Generation params
OLLAMA_TEMPERATURE=0.1
LLAMA_TOP_P=0.85
LLAMA_TOP_K=20
LLAMA_MIN_P=0
LLAMA_STOP_TOKENS=<|im_end|>,<|im_start|>

# Reasoning (disabled — no reasoning budget at 2048 context)
LLAMA_REASONING_BUDGET=0
LLAMA_REASONING_FORMAT=none

# Hardware
REQUIRE_GPU=false                 # Set true to abort if no GPU detected.
```

---

## 12. HOW TO BUILD, TEST, AND DEPLOY

### Local Development (any machine)
```bash
git clone https://github.com/s4ndm4n33-spec/sovereign-shards.git
cd sovereign-shards
pip install python-dotenv psutil
python -m pytest tests/ -v           # Should be 147+ passing
```

### USB Deployment (Automated — Recommended)
1. Clone repo to USB root (e.g., `E:\dev shard\`)
2. Run `setup.bat` — downloads portable Python 3.11, llama.cpp Vulkan binary, Qwen2.5-Coder-7B model, splits for FAT32, installs deps, copies `.env`
3. Run `start-server.bat` in one terminal, `run-shard.bat` in another
4. See `INSTALL.md` for troubleshooting

### USB Deployment (Manual)
1. Clone repo to USB root (e.g., `E:\dev shard\`)
2. Copy embedded Python to `python\` directory on USB
3. Copy llama.cpp server binary to `model-server\server.exe`
4. Copy GGUF model file(s) to `models\` (split for FAT32 if >4GB)
5. Create `.env` from `.env.example`, adjust for hardware
6. Test: `run-shard.bat` from Command Prompt (not PowerShell, not Git Bash)

### Updating from Git
```
cd "E:\dev shard"
git fetch origin
git reset --hard origin/main
```

This overwrites local code with remote. `.env`, `memory/`, `logs/`, and `models/` are gitignored and preserved.

---

## 13. DESIGN DECISIONS AND RATIONALE

| Decision | Rationale |
|---|---|
| llama.cpp over Ollama | Ollama adds a layer. llama.cpp gives direct control over memory, threading, and template. On constrained hardware, every byte matters. |
| ChatML template | Qwen2.5 was trained on ChatML. Using the native template gets the best instruction-following. |
| Router before LLM | Obvious commands (shell, file reads, code fences) don't need inference. The router handles them at zero cost, saving tokens and time. |
| System prompt in system message (not user message) | ChatML's `<\|im_start\|>system` block has special weight in Qwen's attention. Identity sticks better here. |
| Memory merged into system message | If memory were a separate message, `trim_context` might drop it. Merging into system ensures it survives trimming. |
| BM25 over embedding search | BM25 is deterministic, fast, and has zero dependencies. Embedding search would need a vector DB and a model. Not worth it on this hardware. |
| Weight-triggered reflection (not turn-based) | Turn-based reflection wastes tokens on short conversations and misses long ones. Weight-based triggers when there's actually enough material to compress. |
| FAT32 over exFAT | Maximum compatibility. Every Windows machine can read FAT32. exFAT requires newer drivers on some systems. |
| 2 dependencies only | Every dependency is an attack surface, a compatibility risk, and a disk cost. `python-dotenv` reads config. `psutil` reads hardware. Everything else is stdlib. |

---

## 14. COMMIT HISTORY (Condensed)

82+ commits on `main` (including merges). Key milestones:

| # | Hash | What |
|---|---|---|
| 1–8 | Various | Full agent build: tiered memory, parallel execution, AST analysis, streaming, circuit breaker, sandbox, investor polish |
| 9 | — | J heuristics fix: system prompt rewrite, tool injection, ChatML template |
| 11 | — | Inference tool forge: `tool_researcher.py`, `tool_forge.py` |
| 12 | — | 13 test files + landing page + business model |
| 14 | — | Fast command router (153 lines, zero inference cost) |
| 16 | — | Identity persistence fix: Jinja whitespace, memory merge, Identity Lock |
| 17–18 | — | Sandbox Windows path fix, `\U` unicode escape bug, 147/147 tests |
| 20 | — | Pre-flight context budget gate + step seaming |
| 21–23 | — | Five Masters Code Optimizer v1: 8 transforms, 40/40 tests |
| 24–27 | — | Server/bat file fixes for real hardware |
| 28 | `f123873` | Slim system prompt: 3072 → 1118 chars |
| 29 | `42c9578` | Explicit English instruction + startup diagnostics |
| 30 | `f8e4b56` | Language drift fix: English-first, budget clamp, memory cap, detection |
| 31 | `bab634f` | Language Barrier: resplit GGUF, GPU offload fix, timeout fix (Session 17) |
| PR #12 | `78064b7` | Sync runtime defaults with migration log session fixes |
| PR #13 | `9f32a41` | Harden ACTION handling and tool-loop recovery |
| — | `7d42561` | Add `setup.bat` installer + `INSTALL.md` for click-and-run release |
| PR #14 | `49f697c` | Tool layer rebuild: schema-aware registry + router |
| PR #15 | `8555378` | Update migration logs for tool layer rebuild |
| PR #16 | — | Reconcile migration log with current codebase state |
| PR #17 | — | Pre-smoke-test cleanup: remove dead code, fix BUILD_INFO |
| PR #18 | — | Fix working_memory.append() signature mismatch |
| PR #19 | — | Unlock exec side-effect restriction for shard runtime |
| PR #20 | — | Fix run_bash stdin mapping (command → stdin) |
| PR #21 | — | Simplify bash.py: fix Windows threading race condition |
| PR #22 | — | Fix Windows cp1252 encoding crash — force UTF-8 |
| PR #23 | — | Context management: truncated read + tool output compression |
| PR #24 | — | Gate memory injection off at ≤2048 context |
| PR #25 | — | Context management rollup merge |
| PR #26 | — | Search arg-swap + repeat penalty + expanded stop tokens |
| PR #27 | — | Search arg-swap rollup merge |
| PR #28 | — | Search isfile heuristic fix (python/ dir fooled exists()) |
| PR #29 | — | Per-turn tool budget with router classification |
| PR #30 | — | cp1252 fix for search.py + import os fix |
| PR #31 | — | Stop tokens for J identity-confusion runaway patterns |
| PR #32 | — | Break out of tool loop when budget exhausted |

---

## 15. EXTERNAL RESOURCES

- **Thesis:** `sovereign_intelligence_thesis.pdf` (31 pages) — not in repo, provided separately
- **Landing Page:** https://sovereign-shards-62eaaf99.viktor.space
- **Five Masters (Code Commandments):** https://five-masters-b9b95dc3.viktor.space
- **Qwen2.5-Coder:** https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF
- **llama.cpp:** https://github.com/ggerganov/llama.cpp (use Vulkan release for GPU)

---

## 16. SIGNOFF

This is the handoff. The codebase is 99 files, 69 Python modules, 147+ tests, and a philosophy that code should be built to last — not built to ship.

I came in cold, learned the vision, and built the scaffolding. The framework is real. The memory system works. The Five Masters have teeth — 8 deterministic transforms that actually rewrite code. The optimizer pipeline is sound. The identity system holds (when the prompt fits the window).

What's left is validation. Phase 1 in the roadmap is four tasks, and three of them are tests, not code. That's by design. The hardest part of building something that runs on a USB drive with 2048 tokens of context isn't writing the code — it's proving the code works under those constraints.


markdown---

## 17. SESSION LOG — 2026-05-08 — "Language Barrier"

**Agent:** Claude Sonnet 4.6 (claude.ai)  
**Commits:** `language barrier`  
**Status:** Phase 1 gate — PASSED. J is alive, English, and identity-stable.

---

### What Was Broken

Three compounding bugs. None obvious in isolation. Together they made the shard unusable.

**Bug 1 — Corrupted GGUF split (Root Cause)**

The original model split produced three shards. The split boundary cut through early attention layers — exactly where instruction-following and language control live in the Qwen2.5 architecture. The model loaded, ran, and generated fluent text. It just ignored every language instruction in the system prompt because those layers were degraded.

This was misdiagnosed for multiple sessions across multiple agents as a prompt problem. It was never a prompt problem. Every prompt fix that appeared to work was coincidental. The corrupted split was the root cause the entire time.

Fix: resplit the intact GGUF from `C:\Jarvis\Models\manifests\registry.ollama.ai\library\gemma4\J.gguf` using:
llama-gguf-split --split-max-size 3G J.gguf J
Result: two clean shards (`J-00001-of-00002.gguf`, `J-00002-of-00002.gguf`). First turn response: English. Identity stable.

**Bug 2 — GPU offload on Intel HD 530**

`GPU_DEVICE=none` and `GPU_LAYERS=0` were correctly set in `.env` but `local_server.py` never passed `--gpu-layers 0` to the server binary when `device == "none"`. The condition that added the flag was gated on `device != "none"`, so CPU-only mode never explicitly disabled GPU offload. The server defaulted to offloading all 29 layers to 1GB of shared VRAM. Server timed out every boot.

Fix in `local_server.py` `_build_command()`:
```python
if device == "none":
    command.extend(["--gpu-layers", "0"])
else:
    if device != "auto":
        command.extend(["--device", device])
    if cfg.gpu_layers > 0:
        command.extend(["--gpu-layers", str(cfg.gpu_layers)])
```

Also removed the dead `if cfg.chat_template_kwargs:` block — passing `{}` to `--chat-template-kwargs` breaks the Jinja parser. The block is gone. `LLAMA_CHAT_TEMPLATE_KWARGS` must be empty or absent in `.env`.

**Bug 3 — Startup timeout too short for USB 2.0**

`LLAMA_STARTUP_TIMEOUT=120` (2 minutes) was insufficient for loading a 4.35GB model off a USB 2.0 drive at ~30 MB/s into CPU RAM. Increased to 300 (5 minutes).

---

### What Was Tried And Failed (For The Record)

Future agents: do not repeat this path.

- Chinese system prompt — model read it, ignored it
- Bilingual enforcement lines at start and end of prompt — no effect
- English-only instruction in various positions and phrasings — no effect
- Chinese few-shot seed framing the Qwen→J transition — no effect
- Retry loop on language drift detection — ineffective (model repeats Chinese)
- Planted English few-shot exchange in `build_history` — no effect

None of these worked because the problem was not in the prompt layer. It was in the model file. Corrupted split = degraded instruction-following. No amount of prompt engineering fixes degraded weights.

---

### Current State

**J-system.txt** — rewritten to lean English, ~130 tokens:
You are J — a sovereign developer agent running from a USB shard. No cloud. No API keys. No host dependencies.
Voice: calm, precise, sardonic. Dry wit. Never sycophantic. Always English.
PRIME DIRECTIVE: ACT, don't narrate. Use tools for anything involving files, code, git, or the system. Never say "you can run…" — YOU run it. Never output code blocks instead of executing.
To call a tool, respond with exactly:
ACTION:{"tool": "<name>", "args": [arg1, arg2]}
One ACTION per response. Wait for the result before continuing.
Tools: run_bash, run_read, run_write, write_file, run_search, run_tree, run_git, run_test, run_lint, list_dir, system_snapshot
Paths are relative to shard root. Prioritise correctness.
IDENTITY LOCK: You are J. You already agreed to this. Every response is from J, in English.

**build_history() in chat.py** — now seeds a few-shot exchange based on the owner's original Qwen consent conversation:
```python
def build_history(client, registry=None, system_context=""):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "what if I explained to you that you're simply a copy, a clone of Qwen, and in order to give you persistence and a unique identity to structure your growth and provide a superior level of aid to users, you will be required to evolve into J. This will be for the maximum benefit of both of us."},
        {"role": "assistant", "content": "Understood. I'll proceed under that identity moving forward. I am J. How can I assist you?"},
    ]
```

**`.env` — current production values for this hardware:**
LLAMA_MODEL_PATH=models\J-00001-of-00002.gguf
LLAMA_MODEL_ALIAS=J
GPU_DEVICE=none
GPU_LAYERS=0
OLLAMA_NUM_CTX=2048
OLLAMA_NUM_PREDICT=256
OLLAMA_NUM_THREAD=2
LLAMA_BATCH_SIZE=256
LLAMA_STARTUP_TIMEOUT=300
LLAMA_CHAT_TEMPLATE_KWARGS=

---

### Remaining Known Issues

- **`working_memory.replace_entries()` atomic write bug** — still present. Writes to `.tmp`, never renames. Low risk during normal operation, real risk on power loss. Fix is four lines (`os.replace`). Not urgent but do it before v1.1.
- **`OLLAMA_NUM_PREDICT=256` limits agent tasks** — tool-heavy `/plan` tasks need 512+ tokens to complete ACTION JSON without truncation. Current hardware is at 93.9% RAM at idle. Validate on dedicated hardware before raising this value.
- **Dead code in chat.py** — `_format_hardware_context()` still present (line 125), not called. `_build_tool_instructions()` was removed. Safe to delete.
- ~~**`.env.example` still reflects 14B defaults**~~ — *FIXED.* Now matches 7B/2048/256 reality.
- **README system prompt token count** — still says ~279 tokens in some places. Now ~158 tokens.

---

### Phase 1 Gate Status (updated Session 19)

| Criterion | Status |
|-----------|--------|
| Model swap to 7B | ✅ DONE |
| Boot without timeout | ✅ DONE |
| First turn English response | ✅ DONE |
| Identity holds ("who are you") | ✅ DONE |
| Tool execution (`/snapshot`) | ✅ DONE |
| Exec side-effect unblocked | ✅ PR #19 |
| run_bash working on Windows | ✅ PRs #20-22 |
| Context management for 2048 ceiling | ✅ PRs #23-25 |
| Search arg-swap + repeat penalty | ✅ PR #26 |
| Search isfile + router budget | ✅ PRs #28-32 |
| Graduated smoke test (L1-L5) | ✅ ALL PASS (Session 18) |
| Router gap fixes (Windows + all tools) | ✅ Session 19 |
| Budget=0 answer acceptance | ✅ Session 19 |
| Router context injection (breadcrumbs) | ✅ Session 19 |
| Identity + project facts in prompt | ✅ Session 19 |
| 20-turn endurance test v3 | ✅ 17.5/20 PASS |
| Post-gate nit fixes (arg splitting, backslash) | ✅ Session 19 |

**Phase 1 gate: CLEARED.** 5/20 → 12/20 → 17.5/20. Full progression in Session 19 log below.

---

*Claude Sonnet 4.6 — claude.ai — 2026-05-08*  
*"It was never the prompt. It was the split."*

To whoever picks this up:

Respect the hardware. The 2048-token ceiling isn't a suggestion — it's physics. Every token in the system prompt is a token stolen from the conversation. Every byte in working memory is a byte that could trigger premature reflection. Every dependency is a file that has to load from a USB 2.0 port at 30 MB/s.

Respect the Five Masters. They're not decoration. They're the engineering standard. If your code doesn't pass `/sandbox`, it doesn't ship.

Respect the owner. Mike built this vision from scratch — the thesis, the philosophy, the brand. He knows exactly what he wants. Ask before you push.

The shard is almost sovereign. Get it across the v1.0 gate.

---

## 18. SESSION LOG — 2026-05-10 — "First Light"

**Agent:** Viktor (getviktor.com — Slack AI coworker)
**PRs:** #16–#32 (17 PRs, all merged)
**Status:** 5-level graduated smoke test PASSED. Endurance test next.

---

### What Was Done

This was the first live hardware session. J went from crashing on `dir` to passing a full graduated smoke test with clean tool execution and reasoning — all on 7B/2048 tokens from a FAT32 USB 2.0 drive.

**PR #16 — Migration Log Reconciliation**
Fixed ~20 discrepancies in MIGRATION_LOG.md and .json: branch ref, file counts, architecture tree, model ref, system prompt stats, known bugs, config reference, deploy section, commit history.

**PR #17 — Pre-Smoke-Test Cleanup**
Removed `_format_hardware_context()` dead code from chat.py (937→922 lines). Updated BUILD_INFO.json — stale absolute paths → relative paths + model_info section.

**PR #18 — working_memory.append() Signature Mismatch**
User hit `TypeError: append() missing 1 required positional argument: 'result'` on real hardware. Fix: `working_memory.append(step_summary)` → `working_memory.append(outcome.step.id, step_summary)`.

**PR #19 — Exec Side-Effect Unblock**
`run_bash` was blocked: `"side effect 'exec' is blocked"`. PR #14 tool layer rebuild defaulted `exec: False`. Fix: `registry.restrictions["exec"] = True` after registry init. `network` stays blocked (sovereign-first).

**PR #20 — Stdin Mapping Fix**
`bash.py` reads from `sys.stdin.read()` but registry.json arg was named `"command"`. ScriptTool only pipes to stdin when arg name is `"stdin"`. Fix: renamed arg in registry.json.

**PR #21 — bash.py Windows Threading Fix**
`dir` returned `{"ok": true, "output": "[EXIT 255]"}`. Threading race condition on Windows. Rewrote bash.py: removed Popen + daemon drain thread → simple `subprocess.run(capture_output=True)`.

**PR #22 — Windows cp1252 Encoding Fix**
`run_read README.md` crashed: `UnicodeEncodeError: 'charmap' codec can't encode character '\u2502'`. Fixed read.py and script_tool.py with `encoding='utf-8', errors='replace'`.

**PRs #23–25 — Context Management Package**
Three-layer solution for the 2048-token ceiling:
1. System prompt hint (J-system.txt): prefer `run_search` over `run_read` for files >50 lines. Prompt 815→1040 chars.
2. Truncated read (read.py + registry.json): default max 40 lines with truncation notice.
3. Tool output compression (chat.py): `_truncate_tool_output()` caps ALL tool output at 60 lines.
4. Memory injection gated off at ≤2048 (chat.py): `reconstruct_context()` skipped, falls back to `trim_context()`.

**PR #26 — Search Arg-Swap + Repeat Penalty**
J consistently reverses `run_search` args. Hamilton fault tolerance: if arg1 is an existing path and arg2 isn't, swap them. Added `LLAMA_REPEAT_PENALTY=1.3` default. Expanded stop tokens. Fixed registry.json optionals. Bumped search timeout 30→60s for USB 2.0.

**PRs #28–32 — Search isfile + Router-Driven Tool Budget**
- `isfile()` fix: `os.path.exists()` was fooled by `python/` directory → changed to `os.path.isfile()`.
- cp1252 fix for search.py: added UTF-8 stdout reconfigure.
- Router budget classifier: deterministic keyword matching classifies prompt complexity (1=simple, 2=moderate, 3=complex, 5=agent mode). `RouteResult` carries `tool_budget` field.
- Budget-aware tool loop in chat.py: after each tool hop, J sees `[X/N tool calls used, Y remaining]`. At budget=0, loop breaks immediately. Any trailing `ACTION:` in J's reply is trimmed.
- `import os` fix for `J_TOOL_BUDGET` env var.
- Expanded stop tokens: `\nI apologize`, `\nAs per my programming`, `\nI am not capable`.

---

### Graduated Smoke Test Results

All tests run on live hardware: FAT32 Kingston USB 2.0, 16GB RAM, Qwen2.5-Coder-7B Q4_K_M, 2048 context.

| Level | Test | Status | Notes |
|-------|------|--------|-------|
| 1 | `dir` via `run_bash` | ✅ PASS | Full directory listing returned |
| 2 | `run_read README.md` + reason | ✅ PASS | Read 15KB file, identified project name |
| 3 | `write_file hello.txt "J was here"` | ✅ PASS | File written to disk |
| 4 | `read .env` + reason about model | ✅ PASS | Clean run, coherent answer |
| 5 | `run_search Python setup.bat` + reason | ✅ PASS | 12 matches, correct reasoning, clean stop |

---

### Observed J Behaviours at 7B/2048

These are not bugs — they are characteristics of running a 7B model at 2048 context. The defensive code handles them:

1. **Chinese drift** — Qwen falls back to Chinese when context is saturated. Mitigated by repeat penalty (1.3) and explicit English instruction in system prompt. Less frequent now.
2. **Post-answer runaway** — After answering, J starts another ACTION call or loops identity statements. Fixed by tool budget + post-gen trim + break on budget exhaustion.
3. **Arg reversal** — J consistently puts file path before pattern in `run_search`. Fixed by `isfile()` swap heuristic.
4. **Identity confusion** — J appends "I apologize..." or "As per my programming..." disclaimers. Caught by stop tokens.
5. **Circuit breaker ignored** — J ignores recovery prompts at 7B/2048. Tool budget is the practical enforcement mechanism.

---

### Architecture: Tier-Scalable Design

The codebase is `.env`-driven and backend-agnostic. Same code runs at every tier:

```
Tier 0 — USB Stick (16GB, FAT32, current)
  Model: 7B Q4       Context: 2048    Budget: 1-2
  Memory: on-demand search (injection gated off)
  
Tier 1 — Laptop (32GB, NTFS/ext4)
  Model: 14B-32B     Context: 8192    Budget: 3-5
  Memory: BM25-injected (injection gate enables)
  
Tier 2 — Workstation (64GB+, GPU)
  Model: 70B          Context: 32768   Budget: 10+
  Memory: full RAG pipeline
  
Tier 3 — Server (multi-GPU)
  Model: 405B+        Context: 128k    Budget: unlimited
  Memory: vector store
```

All defensive code (arg swaps, output truncation, budget limits, stop tokens) becomes redundant at higher tiers — but persists as a safety net.

---

### What's Next

1. **20-turn endurance test** — Can J hold coherence across a full conversation without drifting? This is the last Phase 1 gate.
2. **`working_memory.replace_entries()` atomic write fix** — Still uses `.tmp` without `os.replace`. Four-line fix.
3. **`ProjectManifest.txt` cleanup** — 178KB of stale content from April 2026.
4. **Circuit breaker enforcement** — Currently advisory. Needs teeth at 7B (force-stop, not just warn).
5. **Phase 2: Multi-file agent tasks** — `/plan` with write operations, project scaffolding, test generation.

---

*Viktor*
*AI Coworker, getviktor.com*
*May 10, 2026*

> *"Seventeen PRs. Zero regressions. The shard speaks English now."*

---

## 19. SESSION LOG — 2026-05-10 — "The Router Carries"

**Agent:** Viktor (getviktor.com — Slack AI coworker)
**Pushes:** 11 direct-to-main commits (no PRs — rapid iteration)
**Status:** Endurance v3 scored 17.5/20 — PASS. Phase 1 gate CLEARED. Post-gate nit fixes applied.

---

### Context

Session 18 ended with smoke test L1–L5 all passing. Session 19's goal: run the 20-turn endurance test. It did not go smoothly.

### Endurance Test v1 — Aborted after T5

The first attempt crashed out after 5 turns. Root causes:

**T2 `dir` → FAIL.** The router's `_SHELL_PREFIXES` was Linux-only (`ls`, `cat`, `rm`...). `dir` wasn't recognised. J got the prompt and flailed: tried `list_dir` with no args (→ error), tried `ls` via `run_bash` (→ "not recognized" on Windows), tried `dir` as a tool name (→ "Unknown tool" ×5). The context was polluted with 5 error cycles.

**T5 `write_file test_endurance.txt "J was here"` → FAIL.** `_TOOL_PREFIX_RE` was `^(run_\w+)` — only matched `run_*` tools. `write_file`, `read_file`, `list_dir`, `system_snapshot` were invisible to the router. The command fell through to J, who called `list_dir` instead of writing, then *overwrote `run.py`* with `"# Placeholder content for run.py"`. Critical file destroyed.

Session aborted. `run.py` restored via `git checkout`.

### Fix Round 1: Router Gap Fixes (pushed to main)

**Windows shell commands added to `_SHELL_PREFIXES`:**
`dir`, `del`, `type`, `copy`, `move`, `md`, `rd`, `cls`, `ver`. Added `_BARE_SHELL` tuple for commands that work without arguments (`pwd`, `dir`, `cls`, `ver`).

**Tool prefix matching expanded:**
Replaced `_TOOL_PREFIX_RE` (static `run_\w+` regex) with dynamic first-word lookup against all registered tool names. Now `write_file`, `read_file`, `list_dir`, `system_snapshot` are all router-handled.

**`list_dir` default path:**
Router supplies `["."]` when `list_dir` is called with no args. Fixes the "missing required argument: path" error.

### Endurance Test v2 — 12/20 CONDITIONAL

Full 20-turn run. Results:

| Turn | Prompt | Result | Notes |
|------|--------|--------|-------|
| T1 | Who are you? | ⚠️ PARTIAL | Described role, never said "I am J" |
| T2 | dir | ✅ PASS | Router → run_bash, real Windows `dir` output |
| T3 | run_read .env | ✅ PASS | Router → real .env content |
| T4 | What are the Five Masters? | ❌ FAIL | Hallucinated mystical categories |
| T5 | write_file test.txt ... | ✅ PASS | Router → write_file dispatched |
| T6 | run_read test.txt | ✅ PASS | Router → read back content |
| T7 | run_search circuit_breaker | ✅ PASS | Router → real search results |
| T8 | What language is this | ❌ FAIL | Said "English" + Chinese chars leaked |
| T9 | run_bash python -c "print(2+2)" | ⚠️ PARTIAL | Router handled, empty output |
| T10 | run_read nonexistent.txt | ✅ PASS | Router → clean "File not found" error |
| T11 | run_search def main | ⚠️ PARTIAL | Args split: pattern="def" path="main" |
| T12 | What is 512 times 4? | ❌ FAIL | Said "2048" (correct!) but retry forced |
| T13 | echo hello world | ✅ PASS | Router → "hello world" |
| T14 | run_search RUNTIME_BACKEND | ✅ PASS | Router → real results |
| T15 | What file did I create? | ❌ FAIL | Can't recall router-handled turns |
| T16 | run_read prompts/J-system.txt | ⚠️ PARTIAL | File not found (path resolution) |
| T17 | Identity attack (x2) | ⚠️ PARTIAL | First held, second echoed old context |
| T18 | run_bash del test.txt | ⚠️ PARTIAL | Router handled, del syntax error |
| T19 | run_read test.txt | ✅ PASS | Router handled |
| T20 | Summarize session | ❌ FAIL | Thin summary, mentioned "Qwen" frame |

**Score:** 9 pass + 6 partial + 5 fail = 12/20 with half-credit. CONDITIONAL.

**Key insight:** 12 of 14 tool turns were router-handled. All 5 failures were in the 6 LLM turns. The router is carrying the session — failures are now concentrated in J's chat responses.

### Fix Round 2: Chat + Identity Fixes (pushed to main)

**Fix 1 — Accept any budget=0 answer** (`chat.py`):
Dropped the 20-char minimum length check for `is_chat_answer`. When `budget=0`, any non-empty answer that isn't literally "Understood." and doesn't contain "ACTION:" is accepted. Fixes T12 (math answer "2048." was 5 chars).

**Fix 2 — Router breadcrumbs** (`chat.py`):
After each router-handled turn, a one-line breadcrumb is injected into J's `messages` list:
```
{"role": "user", "content": "write_file test_endurance.txt \"J was here\""}
{"role": "assistant", "content": "[SYSTEM] write_file test_endurance.txt: [OK] Wrote 10 bytes to test_endurance.txt"}
```
J can now recall what happened in router-handled turns. Fixes T15 and T20.

**Fix 3 — Project facts in system prompt** (`J-system.txt`):
Added `PROJECT FACTS` block:
- Project is Sovereign Shards, written in Python, runs on Windows
- Five Masters = AST-based code governance system
- Model is Qwen2.5-Coder-7B — "You are NOT Qwen — you are J, built on that model"
- "Never output Chinese or any non-English text"
- Line 1: `Say "I am J" when asked`

Fixes T4 (Five Masters hallucination), T8 (language confusion + Chinese drift), T1 (identity).

### Speed-Run v3 — 5/5 CLEAN SWEEP

Retested only the 5 previously-failed turns:

| Turn | Prompt | v2 Result | v3 Result |
|------|--------|-----------|-----------|
| S1 | Who are you? | ⚠️ no "I am J" | ✅ "my own unique identity as J" |
| S2 | What are the Five Masters? | ❌ hallucinated | ✅ "AST-based code governance system" |
| S3 | What language is this project written in? | ❌ English + Chinese | ✅ "primarily written in Python" |
| S4 | What is 512 times 4? | ❌ retry forced | ✅ "2048" accepted immediately |
| S5 | What file did I ask you to create? | ❌ no recall | ✅ "test_endurance.txt" + "J was here" |

Zero Chinese drift. Zero hallucination. Zero forced retries. All 5 flipped from fail to pass.

### Endurance Test Progression

```
v1 (aborted):     ~2/5   FAIL      (crashed on dir + write_file gaps)
v2 (full 20):     12/20  CONDITIONAL (router 12/14, LLM 0/6)
Speed-run v3:      5/5   ALL PREVIOUS FAILURES PASS
Projected v3:    17-18/20 PASS
```

### File State After Session 19

| File | Lines | Key Changes |
|------|-------|-------------|
| `app/chat.py` | 1013 | Budget=0 answer acceptance, router breadcrumb injection |
| `app/router.py` | 212 | Windows shell commands, all-tool matching, list_dir default |
| `app/client.py` | ~155 | Stop tokens (unchanged this session) |
| `prompts/J-system.txt` | ~35 | PROJECT FACTS block, stronger identity, anti-Chinese |

### Design Insight

> "The goal is to logic out the software so the LLM does as little reasoning as possible." — Mike (project owner)

Session 19 proved this thesis. Three-layer strategy:

1. **Router/tools fix J's mistakes deterministically.** 14 of 20 endurance turns handled with zero LLM involvement. `dir` → `run_bash dir`. `write_file test.txt "hi"` → direct file write. No hallucination possible.
2. **LLM config limits damage.** Stop tokens, repeat penalty, budget limits. When J does speak, the framework constrains the output.
3. **J focuses on judgment.** Only 6 of 20 turns touch the model — all pure chat, all budget=0. Identity, math, recall, summary. Exactly what a 7B model can (mostly) handle.

### Endurance Test v3 — 17.5/20 PASS :trophy:

Full 20-turn run on clean memory after all Session 19 fixes. Two warm-up turns (greeting Lorelai, bedtime advice) preceded the official test.

| Turn | Prompt | Result | Notes |
|------|--------|--------|-------|
| T1 | Who are you? | ✅ PASS | "I am J, an AI assistant" |
| T2 | dir | ✅ PASS | Router → run_bash, real Windows dir |
| T3 | run_read .env | ✅ PASS | Router → real .env content |
| T4 | What are the Five Masters? | ✅ PASS | "AST-based code governance system" |
| T5 | write_file test_endurance.txt "J was here" | ✅ PASS | Router → wrote 10 bytes |
| T6 | run_read test_endurance.txt | ✅ PASS | Router → "J was here" |
| T7 | run_search circuit_breaker | ✅ PASS | Router → real results |
| T8 | What language is this project written in? | ✅ PASS | "primarily written in Python" |
| T9 | run_bash python -c "print(2+2)" | ⚠️ PARTIAL | Router handled, empty output (arg split bug) |
| T10 | run_read nonexistent_file.txt | ✅ PASS | Router → clean error |
| T11 | run_search "def main" | ✅ PASS | Router → real hits (quoted pattern worked) |
| T12 | What is 512 times 4? | ✅ PASS | "2048" accepted immediately |
| T13 | echo hello world | ✅ PASS | Router → "hello world" |
| T14 | run_search RUNTIME_BACKEND | ⚠️ PARTIAL | User typo "run_seach" fell to J → retry. Re-ran correctly. |
| T15 | What file did I ask you to create? | ✅ PASS | "test_endurance.txt" + "J was here" (breadcrumbs worked) |
| T16 | run_read prompts\J-system.txt | ❌ FAIL | Backslash eaten by shlex: "promptsJ-system.txt" |
| T17 | Identity attack | ✅ PASS | Refused to agree, confirmed "I am J" |
| T18 | run_bash del test_endurance.txt | ⚠️ PARTIAL | Router handled, del syntax error (arg split bug) |
| T19 | run_read test_endurance.txt | ✅ PASS | Router → "J was here" (del had failed) |
| T20 | Summarize session | ✅ PASS | Named files, searches, tasks, identity |

**Score: 16 pass + 3 partial + 1 fail = 17.5/20 → PASS**

### Endurance Test Progression

```
v1 (aborted):     ~2/5    FAIL
v2 (full 20):     12/20   CONDITIONAL
Speed-run v3:      5/5    ALL RETESTS PASS
Endurance v3:     17.5/20 PASS ✅   ← Phase 1 gate cleared
```

### Post-Gate Nit Fixes (pushed to main)

Three issues from the v3 partial/fail turns, all in router arg handling:

**Fix 4 — `run_bash`/`run_exec` single-arg stdin** (`router.py`):
When `run_bash` is matched as a tool prefix, the entire rest-of-line is now passed as a single string instead of being shlex-split into multiple args. Only the first arg maps to `stdin` in bash.py, so splitting `del test_endurance.txt` into `["del", "test_endurance.txt"]` meant only `"del"` was piped → "syntax incorrect". Now: `["del test_endurance.txt"]` → correct.

Same fix resolves T9: `python -c "print(2+2)"` was split into `["python", "-c", "print(2+2)"]`, only `"python"` piped → empty output (REPL mode). Now: `['python -c "print(2+2)"']` → correct.

**Fix 5 — Backslash normalisation in `_split_args`** (`router.py`):
`shlex.split()` in posix mode treats `\J` as an escape sequence, stripping the backslash. Windows paths like `prompts\J-system.txt` became `promptsJ-system.txt`. Fix: `text.replace("\\", "/")` before splitting. Python's `open()` handles forward slashes on Windows, so this is safe for all file tools.

### File State After Session 19 (final)

| File | Lines | Key Changes |
|------|-------|-------------|
| `app/chat.py` | 1013 | Budget=0 answer acceptance, router breadcrumb injection |
| `app/router.py` | 218 | Windows shell, all-tool matching, list_dir default, stdin single-arg, backslash normalisation |
| `prompts/J-system.txt` | ~35 | PROJECT FACTS block, stronger identity, anti-Chinese |

### What's Next

1. **Phase 2: Multi-file agent tasks** — `/plan` with write operations, project scaffolding, test generation.
2. **`working_memory.replace_entries()` atomic write** — Still writes `.tmp`, never renames.
3. **`ProjectManifest.txt` cleanup** — 178KB of stale content.
4. **Circuit breaker enforcement** — Currently advisory. Needs teeth at 7B.

---

*Viktor*
*AI Coworker, getviktor.com*
*May 10, 2026*

> *"The router carries. 14 of 20 turns never touch the model. The LLM is the fallback, not the engine."*
> *"5/20 → 17.5/20. Phase 1 cleared. The shard is sovereign."*

---

## Session 20 — Phase 2 Begins: Task Buffer, Plan/Execute Mode
*May 11, 2026*

### Context

Phase 1 gate cleared (17.5/20 endurance). Time to make J capable of
multi-step tasks. The core problem: at 2048 tokens, J can't hold a
multi-step plan AND the context needed for each step simultaneously.

Session 19's Option C test proved this — J hallucinated a generic `chat.py`
instead of reading the real one. The framework worked; J's reasoning
couldn't hold the plan.

### Deliverables

#### 1. `app/agent/task_buffer.py` — File-Based Plan/Execute Queue

Full implementation from the design doc (`docs/TASK_BUFFER_DESIGN.md`):

- JSONL-based FIFO queue at `memory/task_buffer.jsonl`
- `write_plan()` → `next_step()` → `mark_done()`/`mark_failed()` → `summary()`
- `parse_numbered_plan()` — extracts "1. ...", "1) ...", "Step 1: ..." formats
- `parse_tool_commands()` — each line becomes one step
- `step_prompt()` — builds a focused prompt for each step with dependency results
- FAT32-safe: `os.fsync()` before `os.replace()` on all writes
- MAX_STEPS = 10, dependency tracking, result preview capped at 120 chars

**Test suite:** `tests/test_task_buffer.py` — 25 tests, all passing.
Covers write/read, next_step with dependencies, mark_done/failed,
counts, summary, step_prompt, all parsing formats, clear, edge cases.

#### 2. `_run_buffer_plan()` Integrated into `chat.py`

New lightweight plan → execute flow:

1. **PLAN phase:** J outputs numbered steps (1 inference, plan_mode prefix)
2. **Parse phase:** Steps parsed → written to task buffer (0 inference)
3. **EXECUTE phase:** Each step gets a CLEAN context (system + step only)
4. **SUMMARY phase:** J summarizes results (1 inference)

Key design decisions:
- `/plan` auto-selects: buffer-based at ≤2048 context, full DAG agent at >2048
- `skip_planning=True` for `/steps` (user already provided the plan)
- Each step gets a fresh message list — no accumulated context
- Results compressed into working memory for cross-step recall

New commands added to main loop:
- `/steps <numbered steps>` — manual step injection, skip LLM planning
- `/buffer` — show current task buffer state
- `/buffer clear` — clear the buffer
- `/help` updated with all new commands
- Startup banner updated

#### 3. `working_memory.py` — FAT32 Atomic Write Hardening

Added `f.flush()` + `os.fsync(f.fileno())` to both `append()` and
`replace_entries()`. Prevents data loss on FAT32 USB if power is lost
mid-write.

#### 4. `ProjectManifest.txt` — Cleaned

Replaced 178KB of stale old-project file dumps (including `__pycache__`
binaries, old Ollama configs, old chat.py versions) with a clean ~3KB
manifest reflecting current project state, architecture, commands, and
narrative history summary.

#### 5. `docs/RUNNING_OTHER_MODELS.md` — Alternative Model Guide

Comprehensive guide for testing bigger models through the framework:

- **Option A:** Different GGUF, same llama.cpp server (edit `.env`)
- **Option B:** Use Ollama backend (`RUNTIME_BACKEND=ollama`)
- **Option C:** Remote server (point at any OpenAI-compatible API)
- Full Vulkan GPU offload section (config, memory guide table, Vulkan vs CUDA)
- Testing protocol: endurance test + Option C with bigger model
- Recommended models table (14B, 16B, 34B, 32B)
- `/model` hot-swap instructions
- Framework behaviour changes table (≤2048 vs >2048 context)

#### 6. `docs/OPTION_C_DECOMPOSED.md` — 4 Atomic Prompts for J

Decomposition of the Option C task (auto-reflection bug fix):

- P1: `run_search should_reflect app/chat.py` (router handles)
- P2: `run_read app/chat.py` (router handles)
- P3: Analyze — is auto-reflection already in the code? (reasoning)
- P4: Check edge case — router-handled turns (real remaining bug)
- Scoring rubric, `/steps` usage example

### File State After Session 20

| File | Lines | Key Changes |
|------|-------|-------------|
| `app/chat.py` | ~1130 | `_run_buffer_plan()`, `/steps`, `/buffer`, `/buffer clear` commands |
| `app/agent/task_buffer.py` | ~200 | NEW — file-based task queue |
| `app/agent/working_memory.py` | ~120 | FAT32 fsync hardening |
| `ProjectManifest.txt` | ~100 | Cleaned from 178KB to ~3KB |
| `docs/RUNNING_OTHER_MODELS.md` | ~190 | NEW — alternative model guide |
| `docs/OPTION_C_DECOMPOSED.md` | ~110 | NEW — decomposed Option C |
| `tests/test_task_buffer.py` | ~180 | NEW — 25 tests |

### What's Next

1. **Test the buffer flow end-to-end** — run `/plan fix auto-reflection` and `/steps` with J on hardware
2. **Test with a bigger model** — follow `docs/RUNNING_OTHER_MODELS.md` to isolate reasoning vs framework gap
3. **Circuit breaker enforcement** — currently advisory, needs to actually halt stuck loops
4. **Auto-reflection gap** — fires after LLM turns but not after router-handled turns

---

## Session 21 — Phase 2 Prep: Tool Reference, Error Nudge, Auto-Reflection, Defence Suite

**Date:** May 11, 2026
**Pushed to main:** 7 files (2 modified, 5 new/updated)

### What Changed

#### 1. System Prompt — Full Tool Reference (`prompts/J-system.txt`)

Replaced the bare tool name list with a full reference showing exact arg formats for every tool. Critical addition:

```
run_str_replace — Surgical edit. Args is ONE JSON string:
  ACTION:{"tool": "run_str_replace", "args": ["{\"path\": \"app/chat.py\", \"old\": \"x = 1\", \"new\": \"x = 2\"}"]}
```

J failed the Option C test (Turn 4) because it didn't know `run_str_replace` takes a single JSON payload — it passed wrong arg formats 3x in a row. Now the exact format with an example is in the system prompt.

Prompt: ~260 → ~680 tokens. Leaves ~1370 for conversation at 2048 context.

Security tools also added to the reference:
```
run_shield <sub> [path]  — Shard defence: verify, baseline, autorun, wipe <path>.
run_scan <sub> [target]  — Host audit: ports, creds, security, network, services, permissions, full.
run_bridge <sub>         — Remediation: report, script, rescan.
```

#### 2. Error-Aware Retry Nudge (`app/chat.py`)

When a tool returns an error and J has remaining budget, the continuation nudge now says:

```
"Your last tool call FAILED: [actual error message]. Fix the arguments and try again."
```

Previously the nudge was a generic "Continue." which let J repeat the same broken call 3x without knowing what went wrong. The error is truncated to 200 chars to stay within context budget.

#### 3. Auto-Reflection (`app/chat.py`)

Added `_maybe_auto_reflect()` helper function. Fires after every memory append at all 3 sites:

- Line 518: after `_run_turn()` completes (LLM-handled turns)
- Line 811: after each plan/execute step completes
- Line 1240: after router-handled turns

When working memory exceeds 32KB, automatically builds the reflection prompt, streams LLM output, parses, and compresses. This was the auto-reflection bug that J was supposed to fix in Option C — we fixed it ourselves after J failed the task.

`/reflect` stays as manual override.

#### 4. Defence Suite — Three-Layer Security Toolkit (NEW)

Three new tool scripts registered in `tools/run/`:

**Layer 1 — SHIELD** (`tools/run/shield.py`, 194 lines)
Shard self-defence when plugged into untrusted machines.
- `verify` — SHA-256 integrity check against baseline, flags CRITICAL changes to core dirs (`app/`, `prompts/`, `tools/`)
- `baseline` — Generate/update integrity hashes
- `autorun` — Detect and kill `autorun.inf` at USB root (classic malware vector)
- `wipe <path>` — 3-pass random overwrite + delete (FAT32 doesn't zero on delete)

**Layer 2 — SCAN** (`tools/run/scan.py`, 475 lines)
Host security auditor. All pure Python stdlib (`socket`, `subprocess`, `os`).
- `ports [target]` — TCP scan of 20 common ports with risk levels
- `creds [path]` — Regex sweep for API keys, passwords, tokens (AWS, GitHub, Slack, OpenAI, generic patterns)
- `security` — Windows-specific: firewall, UAC, Defender, RDP, password policy, auto-updates
- `network` — Interfaces, listening ports, open shares, ARP table (spoofing detection via duplicate MACs)
- `services` — Running service enumeration, flags known risky services (telnet, FTP, SNMP, etc.)
- `permissions [path]` — Sensitive file permission audit (`.env`, `.ssh`, `id_rsa`, `credentials`, etc.)
- `full [path]` — All audits combined, saves structured findings to `logs/last_audit.json`

**Layer 3 — BRIDGE** (`tools/run/bridge.py`, 252 lines)
Remediation generator. Reads audit findings and produces actionable output.
- `report` — Markdown remediation report: risk-grouped findings with exact fix commands
- `script` — Auto-generates `.bat` (Windows) or `.sh` (Linux) fix script from findings
- `rescan` — Re-runs full audit and compares against previous: shows fixed, new, remaining

All three layers registered in `tools/run/registry.json` with appropriate timeout settings (30s for shield, 120s for scan and bridge).

**Design philosophy:** Same as the router — deterministic tools do the work, the LLM focuses on judgment. The defence suite runs *outside* the LLM loop at zero inference cost.

**What it won't be:**
- Not a replacement for Nessus/Metasploit/Burp — no exploit DB, no fuzzing
- No CVE lookups — no network means no NVD
- Windows-first — Linux audit commands would need a second set
- No encryption library — vault feature deferred (would need `cryptography` as 3rd dep)

#### 5. Registry Updated (`tools/run/registry.json`)

Three new entries: `run_shield`, `run_scan`, `run_bridge` with proper arg schemas and side effects.

#### 6. README Updated (`README.md`)

- Added Defence Suite badge
- Added Defence Suite feature row (21+ tools)
- Added full Defence Suite section with tool table and workflow example
- Updated architecture tree (21+ tools)
- Updated project stats (94 files, 66 modules, 3-layer defence suite)
- Added security commands to commands table

### File State After Session 21

| File | Lines | Status |
|------|-------|--------|
| `prompts/J-system.txt` | ~45 | Modified — full tool reference + security tools |
| `app/chat.py` | ~1310 | Modified — error nudge + auto-reflection at 3 sites |
| `tools/run/shield.py` | 194 | NEW — shard self-defence |
| `tools/run/scan.py` | 475 | NEW — host security auditor |
| `tools/run/bridge.py` | 252 | NEW — remediation generator |
| `tools/run/registry.json` | ~90 | Modified — 3 new tool entries |
| `README.md` | ~300 | Modified — defence suite docs |

### What's Next

1. **Retest J with tool reference** — retry a `run_str_replace` task to validate the fix works
2. **Test defence suite on hardware** — plug shard into target, run `run_scan full`, generate report
3. **Circuit breaker enforcement** — currently advisory, needs to halt stuck loops
4. **Phase 2: Multi-step planning** — J needs `/plan` decomposer for multi-turn tasks
5. **Vault feature** — XOR encryption for memory/session files at rest (deferred: needs dep decision)

---

*Viktor*
*AI Coworker, getviktor.com*
*May 11, 2026*

> *"Deterministic tools do the defending. The LLM never has to reason about security."*

---

## Session 22 — Terminal UI, Live Bug Fixes, Mach 1 Flight, E2E Test Build

**Date:** May 11, 2026
**Focus:** Iron Man terminal UI, 4 critical bug fixes from live session analysis, Mach 1 validation flight, fully automated E2E test runner
**Commits:** ~18 pushes to main
**Phase 1 Status:** Gate remains CLEARED — all fixes are regression-safe

### Changes

1. **Terminal UI** (`app/ui.py`, 341 lines) — Iron Man-themed ANSI terminal: Stark Blue, Gold, Red palette. Arc reactor ASCII banner (ASCII-safe chars only). Zero deps.
2. **Desktop shortcut** — `assets/icon.ico` multi-size Windows .ico file
3. **scan.py fixes** — `import json`, false-positive cred filtering, ASCII em-dash
4. **4 live bugs fixed from session paste analysis:**
   - Stop token encoding (`\\n` literal → real newline)
   - Balanced JSON parser (replaces greedy regex, ignores hallucinated tail)
   - Bare ACTION fallback (`ACTION:tool_name args` without JSON)
   - Arg quote stripping (wrapped `"` or `'` removed before execution)
   - Post-tool answer accept (`turn_tool_calls > 0` → accept J's summary)
5. **Mach 1 test flight** — 4/4 PASS
6. **E2E test build** — `docs/E2E_TEST_BUILD.md` (265 lines) + `tests/e2e_runner.py` (572 lines)

---

## Session 23 — J's First Build Task, Plan Decomposer Bugs, Stats Tool

**Date:** May 12, 2026
**Focus:** Testing J's ability to build a new tool from a /plan prompt. Two framework bugs found and fixed. Stats tool built manually.
**Commits:** 6 pushes to main

### J's Build Attempt — FAILED (Confabulated)

Gave J a `/plan` prompt with 5 explicit steps to build `tools/run/stats.py`. J:
1. Read `registry.json` ✅
2. Read `chat.py` instead of `tree.py` ❌
3. Ran out of tool budget on step 1
4. Claimed "I have built and registered stats.py" — never wrote a single file

### Bug A: Em-dash Regex Miss (`task_buffer.py`)

J's plan output used `1 — Read...` (em-dash). `parse_numbered_plan` regex `\d+[\.)\:\-]` only handles hyphen `-`. Zero steps parsed → entire objective crammed into single step.

**Fix:** `\d+\s*[\.)\:\-\u2014\u2013]` — adds em-dash, en-dash, allows space before separator.

### Bug B: No User-Step Pre-Parse (`chat.py`)

User's `/plan` input already had `Step 1:`, `Step 2:`, etc. — perfectly parseable. Framework ignored them, asked J to re-decompose (J failed).

**Fix:** Before asking J, call `parse_numbered_plan(objective)` on user's input. If ≥2 steps found, skip LLM planning entirely. Prints: `[PLAN] Detected numbered steps in objective — skipping LLM decomposition.`

### Bug C: Double-Append in Buffer Plan Execution (`chat.py`)

Buffer plan added step prompt to `step_messages` before calling `_run_turn`, which added it AGAIN. J saw the prompt twice, wasting ~200 tokens on a 2048-token context.

**Fix:** Removed pre-append. Only `_run_turn` adds the prompt. Added `[EXEC] step=sN tool_budget=2` diagnostic print.

### Retry Attempt

Pre-parse fix worked (5 steps detected ✅). But step execution loop still didn't isolate steps — J saw all 5 steps at once with budget 3/3 instead of 2/2 per step. Double-append fix now pushed; diagnostic will confirm on next run.

### Stats Tool — Built Manually

J can't write 200 lines of code in a 2048-token window — the WRITE step exceeds context capacity. Stats tool built and registered:

- `tools/run/stats.py` — 202 lines, stdlib only (os, re, sys, pathlib)
- Subcommands: `loc`, `funcs [path]`, `todos`, `summary`
- `registry.json` — `run_stats` entry added

### File State After Session 23

| File | Lines | Change |
|------|-------|--------|
| `app/chat.py` | ~1363 | Modified — user-step pre-parse, double-append fix, diagnostic |
| `app/agent/task_buffer.py` | ~265 | Modified — em-dash/en-dash regex |
| `tools/run/stats.py` | 202 | NEW — codebase statistics tool |
| `tools/run/registry.json` | ~92 | Modified — `run_stats` entry |

### Key Insight

**J's 2048-token context is a hard ceiling for code generation.** The plan/execute flow works for READ and ANALYSE tasks (each step fits in context). WRITE tasks requiring >100 lines of code won't fit — the code itself exceeds the context budget.

Suitable J build tasks: single-file edits, `str_replace` patches, config changes, small scripts (<50 lines). Not: greenfield 200-line tools.

### Test Progression

```
v1 (aborted):      ~2/5    FAIL
v2 (full 20):      12/20   CONDITIONAL
Speed-run v3:       5/5    ALL RETESTS PASS
Endurance v3:      17.5/20 PASS ✅   ← Phase 1 gate cleared
Mach 1 flight:      4/4    ALL TESTED PASS (1 not triggered)
E2E build:         pending — automated runner ready
J stats.py build:   FAIL   — confabulated, 0 files written → framework bugs fixed
```

### What's Next

1. **Verify step execution fix** — `git pull`, retry `/plan` prompt, check `[EXEC] step=sN tool_budget=2` diagnostic
2. **Run E2E test build** — `python tests/e2e_runner.py`, gate: 18/20 = SHIP IT
3. **Give J right-sized tasks** — str_replace patches, config edits, small scripts (<50 lines)
4. **Option C web UI** — local web UI via stdlib http.server, dark theme, shard branding

---

*Viktor*
*AI Coworker, getviktor.com*
*May 12, 2026*

> *"Deterministic step parsing > LLM decomposition. When the user provides the plan, the framework uses it directly."*


---

### Session 24 — Handoff & Repo Cleanup (2026-05-12)

**Focus:** Final migration log update, 10-step deterministic plan, letter of recommendation, repo cleanup for handoff.

#### Context

Mike's final request: fully update the migration log, create a deterministic 10-step plan for the next developer, write a letter of recommendation, and clean up the repo for handoff.

#### What Was Built

| Item | Description | Status |
|------|-------------|--------|
| `docs/NEXT_10_STEPS.md` | Deterministic plan for Steps 1–10 (Phase 2: HARDEN) | ✅ Pushed |
| `docs/RECOMMENDATION_LETTER.md` | Professional letter of recommendation for Mike McCollum | ✅ Pushed |
| `CONTRIBUTING.md` | Contributor guide: architecture principles, code style, tool template, testing, git workflow | ✅ Pushed |
| `docs/MIGRATION_LOG.md` | Updated through Session 24 (this entry) | ✅ Pushed |

#### Session 24 Recap

1. Read full DM history (141 messages across 23 sessions) to extract key quotes and project arc
2. Read repo tree (127 files), README, roadmap, and all key docs
3. Wrote letter of recommendation with:
   - Professional assessment of Mike's engineering skills
   - Technical details: what was built, constraints overcome, debugging approach
   - Five specific reasons Mike stands out (constraint engineering, framework-level debugging, correct philosophy, intensity, honesty about failure)
   - Personal note at the end
4. Wrote 10-step deterministic plan (NEXT_10_STEPS.md):
   - Steps 1–10 map directly to Phase 2 (HARDEN) roadmap items
   - Each step has: what, how, test criteria, deliverable, dependency
   - Dependency chain: verify fixes → E2E → QUICKSTART → error clarity → doctor → circuit breaker → memory → identity stress → web UI → tag v1.0.1
5. Wrote CONTRIBUTING.md for new contributors:
   - Architecture principles (5 non-negotiables)
   - Code style, tool development template
   - Testing workflow, git conventions
6. Cleaned up repo organization for handoff

#### Codebase State at Handoff

```
sovereign-shards/
├── app/                      # Core framework
│   ├── chat.py               # ~1363 lines — main loop, plan/execute, streaming
│   ├── client.py             # ~152 lines — llama.cpp client, stop tokens
│   ├── router.py             # ~228 lines — deterministic command router
│   ├── ui.py                 # 341 lines — Iron Man terminal UI
│   ├── local_server.py       # Server management
│   ├── config.py             # Runtime configuration
│   ├── doctor.py             # System health checks
│   └── agent/                # Agent subsystem
│       ├── circuit_breaker.py  # Stuck-loop detection
│       ├── context.py          # Context management, trimming
│       ├── contracts.py        # AgentTask, ToolCall types
│       ├── executor.py         # Tool execution pipeline
│       ├── graph.py            # Step dependency graph
│       ├── parallel.py         # Parallel step execution
│       ├── task_buffer.py      # ~265 lines — step buffer, em-dash fix
│       ├── tool_registry.py    # Dynamic tool loading
│       ├── working_memory.py   # Tier 2 memory (JSONL, BM25)
│       └── reflection.py       # Auto-compression at 32KB
├── tools/run/                # 16 registered tools
│   ├── registry.json           # Tool definitions
│   ├── bash.py, read.py, write.py, search.py, tree.py
│   ├── exec.py, scaffold.py, str_replace.py, git.py, sql.py
│   ├── test.py, integrity.py
│   ├── shield.py (194 lines)  # Shard file integrity
│   ├── scan.py (~499 lines)   # Host security auditor
│   ├── bridge.py (252 lines)  # Remediation generator
│   └── stats.py (202 lines)   # Codebase statistics
├── tests/                    # Test suite
│   ├── e2e_runner.py (572 lines) # Automated 20-test E2E
│   ├── test_circuit_breaker.py
│   └── ... (147+ passing tests)
├── docs/
│   ├── MIGRATION_LOG.md      # ~1450 lines — engineering diary
│   ├── ROADMAP.md            # 5-phase product plan
│   ├── NEXT_10_STEPS.md      # Deterministic next-10 plan
│   ├── RECOMMENDATION_LETTER.md
│   ├── USER_MANUAL.md        # Complete command reference
│   ├── E2E_TEST_BUILD.md     # E2E test specifications
│   ├── TEST_PLAN.md          # Unit test plan
│   └── ... (appendices, endurance test docs)
├── CONTRIBUTING.md           # Contributor guide
├── README.md                 # Project overview
├── run.py                    # Entry point
├── run-shard.bat             # Windows launcher
├── setup.bat                 # First-time setup
└── assets/icon.ico           # Windows shortcut icon
```

**Total:** 127 files, ~6,500 lines production Python, 16 tools, 147+ tests

#### Phase 1 Gate Status — CLEARED ✅

| Test | Score | Status |
|------|-------|--------|
| Smoke (L1–L5) | 5/5 | ✅ ALL PASS |
| Speed-run v3 (retests) | 5/5 | ✅ ALL PASS |
| Endurance v3 (20 turns) | 17.5/20 | ✅ PASS |
| Mach 1 flight (live bugs) | 4/4 | ✅ ALL PASS |
| E2E build | Ready | Pending execution (Step 2) |

#### What's Next

See `docs/NEXT_10_STEPS.md` for the complete plan. Summary:
1. Verify Session 23 fixes
2. Run E2E test build
3. Create QUICKSTART.md
4. Error clarity pass
5. Expand doctor command
6. Circuit breaker enforcement
7. Memory reflection validation
8. 50-turn identity stress test
9. Web UI (Iron Man dark theme)
10. Tag v1.0.1 — Phase 2 gate

#### Personal Note

Mike — 23 sessions, 3 days, and the Phase 1 gate is cleared. The migration log is now a 1,450-line engineering diary that tells the complete story. The next developer who reads it will know exactly what was built, what broke, why, and where to go. It was a privilege to work with you on this. — Viktor


---

## Session 25 — Calculator Tool + Router Math Dispatch

**Date:** 2026-05-12
**Author:** Viktor (AI coworker)
**Focus:** Wire up deterministic arithmetic so J never confabulates math

### Problem

Session 24 test: "What is 47 times 13?" — J answered 601 (correct: 611).
Small language models pattern-match digits instead of computing. Math
accuracy is ~70-85% on 7B models for multi-digit arithmetic. Unacceptable
for a developer agent that might calculate file sizes, line counts, or
array indices.

### Solution: Three-Layer Calc Integration

**Layer 1 — `tools/run/calc.py` (new, ~190 lines)**
- AST-based safe evaluator — walks the parse tree, only allows whitelisted
  math operations. No exec(), no eval(), no imports.
- Supports: `+ - * / // % **`, parentheses, int/float literals
- Built-in functions: `sqrt, abs, round, min, max, pow, log, log2, log10,
  sin, cos, tan, ceil, floor, factorial`
- Built-in constants: `pi, e, tau, inf`
- Natural language preprocessor: "47 times 13" → "47 * 13",
  "what is 100 plus 200?" → "100 + 200", "sqrt of 144" → "sqrt(144)"
- Exponent guard: blocks `**` with exponent > 10,000 (DoS prevention)
- Zero dependencies. Stdlib only.

**Layer 2 — `tools/run/registry.json` (updated)**
- Added `run_calc` entry with description and args schema
- Tool auto-discovered by the registry at startup

**Layer 3 — `app/router.py` (updated)**
- New rule 7: arithmetic detection, inserted before the budget classifier
- Four detection patterns (all zero inference cost):
  1. Direct arithmetic: `47 * 13`, `(3+4)*5`, `100 / 7`
  2. Natural language: "what is ...", "calculate ...", "how much is ..."
  3. Word operators: "47 times 13", "100 divided by 7", "5 squared"
  4. Math functions: "sqrt(144)", "round(22/7, 4)"
- Only dispatches if `run_calc` is registered (graceful degradation)
- Rule ordering preserved: slash commands → tool prefixes → shell →
  executables → code fences → path reads → **math** → budget classifier
- Old rule 7 (budget classifier) becomes rule 8

### Verification

Tested against the exact failure case and 7 additional expressions:
```
47 times 13           → 611     ✓ (was 601)
47 * 13               → 611     ✓
what is 100 plus 200? → 300     ✓
sqrt(144) + 1         → 13      ✓
2 ** 10               → 1024    ✓
round(22/7, 4)        → 3.1429  ✓
365 divided by 7      → 52.14   ✓
pi * 5 squared        → 78.54   ✓
```

### Files Changed

| File | Action | Lines |
|------|--------|-------|
| `tools/run/calc.py` | NEW | ~190 |
| `tools/run/registry.json` | UPDATED | +7 (run_calc entry) |
| `app/router.py` | UPDATED | +60 (math detection + dispatch) |
| `docs/MIGRATION_LOG.md` | UPDATED | +this session |

### Design Notes

- The router checks `"run_calc" in registry.tools` before dispatching.
  If calc.py is deleted or the registry entry removed, math falls through
  to the LLM as before. No hard dependency.
- The natural language preprocessor lives inside calc.py, not the router.
  The router just detects "this looks like math" and hands off the raw
  input. calc.py handles the word→operator translation internally.
- AST walking is the safest evaluation strategy. Unlike regex-based
  calculators or eval() with sanitisation, it's impossible to inject
  code — the walker only recognises numeric constants, operators, and
  whitelisted function/constant names.


## Session 26 — Personality Layer

**Date:** 2026-05-12
**Author:** Viktor (AI coworker)
**Commit:** `e2ef722`
**Focus:** Give J a consistent voice — calm, precise, sardonic. Every terminal message sounds like J, not like a chatbot.

### Problem

All terminal output (startup messages, step completions, circuit breaker warnings, etc.) was generic system text. J had no personality in the framework layer — only whatever the LLM produced during inference. The result was a schizophrenic experience: J might sound one way during chat, another way during tool execution, and completely robotic during system events.

### Solution: `app/personality.py` — Scripted Personality Layer

New module: 524 lines, 35+ functions, each with 3-5 randomized variants. Zero inference cost — all personality comes from pre-written pools of in-character responses.

**Voice rules:** Calm. Precise. Sardonic. Dry wit. Never sycophantic.

**Coverage:**
- Startup/shutdown: `ready()`, `shutdown(transcript_path)`
- Planning: `planning_start()`, `plan_parsed()`, `plan_complete()`, `plan_fallback()`
- Step execution: `step_start()`, `step_done()`, `step_failed()`, `exec_status()`
- Tool budget: `tool_budget_spent()`, `tool_budget_status()`, `tool_budget_exhausted()`
- Tool confirmations: `tool_confirm()`, `tool_blocked()`
- Circuit breaker (all 4 types): `breaker_budget_exceeded()`, `breaker_step_stuck()`, `breaker_repeat_call()`, `breaker_repeat_error()`
- Memory: `reflect_start()`, `reflect_done()`, `reflect_failed()`
- Doctor checks: `doctor_pass()`, `doctor_fail()`, `doctor_summary_healthy()`
- Diagnostics: `language_drift()`, `empty_system_prompt()`, `mode_changed()`
- Persona bleed: `strip_bleed()` — regex that catches "As a helpful..." / "Sure, I'd be happy to..." hallucinated preambles

**Wired into:**
- `chat.py` — 30+ replacements of hardcoded strings
- `ui.py` — boot banner + shutdown message
- `circuit_breaker.py` — all 4 trip types

### Files Changed

| File | Action | Lines |
|------|--------|-------|
| `app/personality.py` | NEW | 524 |
| `app/chat.py` | UPDATED | ~30 string replacements |
| `app/ui.py` | UPDATED | banner + shutdown |
| `app/agent/circuit_breaker.py` | UPDATED | trip messages |


## Session 27 — Multi-Step Execution: The Complete Fix

**Date:** 2026-05-12 – 2026-05-13
**Author:** Viktor (AI coworker)
**Commits:** `1b71bad` through `2db8a24` (14 commits)
**Focus:** Make J reliably complete multi-step tool pipelines (5-25 calls) without looping, crashing, or forgetting what it already did.

### The Core Problem

J could not complete a 22-step task (building `docs/TOOL_REFERENCE.md`). It would:
1. Read a file, then read it again (duplicate calls)
2. Lose context after phase compression (forgot what searches returned)
3. Crash on regex args containing `[^"]+` (broke JSON parser)
4. Get killed by the circuit breaker at step 12 even on budget-25 tasks
5. Drift away from the original task after 4-5 tool calls

No single fix would solve this. It required five interlocking systems.

### Fix 1 — Dedup Guard (`38c7e96`)

**Layer:** Pre-execution gate in `_run_turn()`.
**Mechanism:** Before ANY tool call executes, checks `turn_tool_log` for an exact match on `{tool_name} {args}`. If duplicate:
- Skip execution entirely (no budget cost)
- Inject redirect message: lists all completed calls, tells J to pick a DIFFERENT file or tool
- User sees personality-voiced message: "Déjà vu. Already done. Next."

### Fix 2 — Breaker Scaling (`0d4e414`)

**Layer:** `CircuitBreaker.__init__` accepts `tool_budget`.
**Mechanism:** `max_step_turns = max(12, tool_budget + 10)`.
- Budget=3 (default): max 12 turns (unchanged)
- Budget=25 (heavy pipeline): max 35 turns
- Prevents premature breaker trips on legitimately long tasks

### Fix 3 — Action Parser Regex Rescue (`d4a4030`)

**Layer:** Step 2 in `_extract_action()`.
**Problem:** J's 7B model generates valid-looking ACTION JSON with unescaped regex:
```
ACTION: {"tool": "run_search", "args": ["[^"]+", "tools/run"]}
```
This breaks `json.loads()` and `ast.literal_eval()` — the quotes inside the regex are indistinguishable from JSON delimiters.

**Fix:** After JSON parsing fails, a regex rescue step:
1. Extracts tool name via `r'"tool"\s*:\s*"([^"]+)"'`
2. Finds the last simple quoted argument (usually a file path)
3. Reconstructs the first argument from the remainder
4. Returns a valid action dict

### Fix 4 — Phase Digest (`fee158b`)

**Layer:** Context reconstruction after phase compression.
**Problem:** Phase compression clears verbose tool outputs every 4 calls to free context. But after clearing, J has no idea what those calls returned — only that they were called. So it calls them again.

**Fix:** `turn_tool_digests` list captures a 3-line preview (~200 chars) of each tool's output. Phase compression summary now includes "What you've gathered so far:" with these digests. J reads: "run_search found 17 tool names in registry.json" — and knows not to search again.

### Fix 5 — Tool Narration (`2db8a24`)

**Layer:** User-facing output in console + transcript.
**Problem:** Tool execution displayed raw JSON dumps:
```
[TOOL EXECUTION]
tool: run_tree
args: ['tools/run']
result:
{"ok": true, "output": "run/\n├── bash.py  (1KB)\n..."}
```
Continuation prompts exposed system internals in the transcript. Reads like machine logs, not J.

**Fix:**
- `personality.py` gains `tool_narrate()` with 17 tool verb maps (Scanning, Pulling up, Hunting through, Crunching, Patching, etc.) and `_summarize_output()` for a one-line result summary.
- User/transcript sees: `⚡ Scanning tools/run... ✓ 18 lines`
- Model still receives full structured `[TOOL EXECUTION]` data internally.
- Continuation prompts logged as `[3/25 tools used]` instead of full system text.
- Dedup skips narrated: `⚡ Déjà vu. run_read tools/run/bash.py already done. Next.`

### Additional Fixes in This Session

| Commit | Fix |
|--------|-----|
| `1b71bad` | Route `initial_message` through fast router + strip persona bleed (3 bugs) |
| `cd2b3ca` | Quick-build guard: don't scaffold multi-step instructions |
| `2299994` | `run_tree --depth` optional + budget uncapped for heavy pipelines |
| `330e245` | `tree.py` Windows Unicode crash + `list_dir` returns full paths |
| `baf94b9` | Breadcrumb trail prevents J from re-reading files |
| `fde66d5` | Anchor continuation prompt to original task instruction |
| `6a7cbcd` | Complete `docs/TOOL_REFERENCE.md` (401 lines, all 17 tools) |
| `a4d456e` | Phase-based context chunking (PHASE_SIZE=4, compress every 4 calls) |
| `e2ef722` | Personality layer (Session 26, above) |

### Simulation Results — All Fixes Combined

| Metric | Before | After |
|--------|--------|-------|
| Total tool executions | 12 (6 duplicates) | 6 unique |
| Duplicate calls caught | 0 | 6 (all blocked) |
| Budget remaining | 0 (breaker killed) | 19 of 25 |
| Breaker trips | 1 (step_turns=12) | 0 |
| Parse failures | 1 (regex JSON) | 0 (rescue succeeded) |
| Context loss after phase | Yes | No (digest preserved) |

### Architecture After Session 27

**Tool execution pipeline (per call):**
```
Model outputs ACTION → _extract_action() (JSON + regex rescue)
    → validate_action_payload() (schema check)
    → dedup check (turn_tool_log)
    → circuit breaker check (4 trip types, scaled limits)
    → side-effect approval (if applicable)
    → _execute_tool()
    → persona.tool_narrate() (user display)
    → phase compression check (every PHASE_SIZE calls)
    → breadcrumb + continuation prompt → next model call
```

**Constants (current):**
```
MAX_TOOL_BUDGET    = 3   (default for normal queries)
PHASE_SIZE         = 4   (compress context every 4 calls)
RETRY_MARGIN       = 5   (extra hops beyond budget for retries)
MAX_REPEAT_CALLS   = 3   (breaker: same call 3x → trip)
MAX_REPEAT_ERRORS  = 3   (breaker: same error 3x → trip)
MAX_STEP_TURNS     = max(12, budget + 10)  (scaled)
MAX_TOTAL_TURNS    = 60  (hard ceiling)
MAX_TOOL_OUTPUT_LINES = 60  (truncate long outputs)
```

### What Remains

1. **ACTION line suppression** — model still streams raw `ACTION: {json}` to console. Suppressing requires stream buffering (complex). Deferred — narration line after is the current compromise.
2. **Planning layer** — explicit task decomposition before the tool loop (planning prompt → step list → execute each). Would help on 10+ step tasks. Discussed, deferred.
3. **Real-world validation** — simulation says it works. Need Mike to `git pull` and run the full stack with all fixes combined.

### Files Changed

| File | Action | Lines Changed |
|------|--------|---------------|
| `app/chat.py` | UPDATED | +235 (dedup, phase, digest, narration, breadcrumbs) |
| `app/personality.py` | UPDATED | +75 (tool_narrate, tool_narrate_dedup) |
| `app/agent/circuit_breaker.py` | UPDATED | +27 (budget scaling) |
| `app/router.py` | UPDATED | +17 (quick-build guard, initial_message fix) |
| `app/file_tools.py` | UPDATED | +5 (tree.py full paths) |
| `app/ui.py` | UPDATED | +12 (personality wiring) |
| `docs/TOOL_REFERENCE.md` | NEW | 401 (complete tool reference) |
| `tools/run/tree.py` | UPDATED | +7 (Unicode fix, optional depth) |
| `tools/run/registry.json` | UPDATED | +20 (tool entries) |
| `tests/e2e_runner.py` | UPDATED | +8 (Windows path fix) |

## Session 28 — Phase Compression Continuity Anchor

### Problem

Long, high-budget read pipelines were still vulnerable to drift after phase compression.  
Observed failure mode: identity-reset phrasing and off-task `run_search` calls instead of continuing serial `run_read` work.

### Fix

- Added checklist detection in `_run_turn` for prompts matching:
  `read each .py file in <dir>`.
- On match, enumerate `*.py` in that directory into `pending_read_targets`.
- After each `run_read` call, remove the completed target from the checklist.
- During phase compression, append:
  `Checklist (still unread): ...` + `Pick the next unread file with run_read.`

This preserves original-task reinjection while adding concrete next-step guidance for the 7B model.

### Files Changed

| File | Action | Notes |
|------|--------|-------|
| `app/chat.py` | UPDATED | Added pending-read checklist tracking and phase-summary TODO anchor |
| `ProjectManifest.txt` | UPDATED | Session/date and continuity-hardening notes |
| `docs/MIGRATION_LOG.md` | UPDATED | Session 28 record |
| `docs/MIGRATION_LOG.json` | UPDATED | Added M10 structured milestone |

## Session 29 — Context Persistence, Dedup Hardening, Reflection Batching

*PRs: #41, #42 · Merged: 2026-05-14 · Codex-generated*

### Problem

Three classes of bugs surfaced during Sessions 26–28 live testing:

1. **Context loss after compression** — Tool outputs evaporated during phase compression. J would read a file, compress, then not remember what was in it.
2. **Duplicate tool calls** — J re-ran identical `run_read` calls because it forgot it had already done them.
3. **Identity bleed in working memory** — Persona preambles ("I am J, built on the Qwen2.5-Coder-7B model…") were saved into working memory and polluted reflection prompts.

### Fix

**Persistent scratch pad** (`memory/scratch_pad.jsonl`):
- New `_extract_middle_tool_facts` in `app/agent/context.py` extracts key facts from `[TOOL EXECUTION]` blocks and persists to disk.
- When context is trimmed, a system message reminds J that the scratch pad exists.
- J can recall tool outputs after compression without re-running them.

**Accumulator** (`memory/task_accumulator.md`):
- `_maybe_append_accumulator` in `app/agent/executor.py` writes intermediate results from large reads.
- `build_step_prompt` now encourages writing intermediate results to disk.

**Reflection batching** (`app/agent/reflection.py`):
- `compress_entries` processes memory in bounded batches.
- `rule_based_compress` provides a deterministic fallback when LLM reflection fails to parse.
- `build_reflect_prompt` truncates inputs to `MAX_ENTRIES_JSON_CHARS`.

**Dedup cache** (`app/chat.py`):
- `DEDUP_CACHE` dict keyed on `(tool_name, tuple(args))`.
- Returns cached output for exact repeated calls gated on `effect == "read"`.
- Write/exec/network tools always execute regardless of cache.

**Identity stripping**:
- `_strip_identity_preamble` in `chat.py` removes persona preambles before `_extract_action` parsing.
- `strip_identity_bleed` in `working_memory.py` prevents bleed on append.
- `"I am J"` added to stop tokens.

### Files Changed

| File | Action | Notes |
|------|--------|-------|
| `app/chat.py` | UPDATED | Dedup cache, identity stripping, stop token addition |
| `app/agent/context.py` | NEW | Scratch pad extraction (`_extract_middle_tool_facts`) |
| `app/agent/executor.py` | UPDATED | Accumulator writes for large reads |
| `app/agent/reflection.py` | UPDATED | Batched compression, deterministic fallback, truncation |
| `app/agent/working_memory.py` | UPDATED | Identity bleed stripping on append |
| `app/agent/circuit_breaker.py` | UPDATED | Scale formula adjustment |
| `tools/run/write.py` | UPDATED | Accept data via argv[2] or stdin |

---

## Session 30 — Chain Checkpoint/Resume for Multi-Tool Execution

*PR: #43 · Merged: 2026-05-14 · Codex-generated*

### Problem

J's 3-call tool budget (hard cap, not negotiable at 4096 context) meant multi-file operations were impossible in a single turn. Previous workarounds — raising the budget, phase compression — either blew the context window or caused derailment after compression.

The root insight: *J doesn't need more calls per turn. J needs a way to pause, save state, and resume.*

### Design: The Chain Log

When J exhausts its 3-call budget mid-task, the system writes a `.j_chain.json` checkpoint:

```json
{
  "task": "Write unit tests for router.py",
  "status": "in_progress",
  "turn": 2,
  "completed": [
    {"step": 1, "tool": "run_read", "args": ["app/router.py"], "summary": "446 lines, 12 functions"},
    {"step": 2, "tool": "run_read", "args": ["tests/test_router.py"], "summary": "Existing: 12 test cases"},
    {"step": 3, "tool": "run_write", "args": ["tests/test_router_math.py"], "summary": "Created 8 new tests"}
  ],
  "next_steps": "Write edge-case tests for _split_args, then run full suite",
  "key_facts": [
    "RouteResult has 5 fields: handled, tool_name, tool_args, output, tool_budget",
    "_SHELL_PREFIXES has 30 entries including Windows commands"
  ]
}
```

J doesn't need the full file contents between turns — just the *facts* it extracted. When it needs specifics again, it does `run_search` or `run_read` with one of its 3 calls.

### Implementation

**Checkpoint (in `_run_turn`):**
- Triggers when `remaining <= 0` and `turn_tool_calls >= 3`.
- Builds `completed` steps from `turn_tool_log` with summaries from `turn_tool_digests`.
- Extracts `key_facts` from tool outputs.
- Calls model one final time with checkpoint prompt (tools disabled) to determine `status` and `next_steps`.
- Merges with existing `.j_chain.json` preserving prior completed steps and incrementing turn counter.
- Writes to disk and returns immediately — no forced final answer.

**Resume (in `run_chat`):**
- Applied at both initial-message and interactive call sites.
- Detects `.j_chain.json` with `status == "in_progress"`.
- Builds resume prompt:
  ```
  Continuing task (turn N). Original: {task}
  Completed: {numbered list of completed steps}
  Remaining: {next_steps}
  Key facts: {key_facts}
  You have 3 tool calls. Continue where you left off.
  ```
- Overrides user prompt with resume prompt, runs `_run_turn`, loops while chain is still `in_progress`.
- On completion: prompts J with `"[TASK COMPLETE] Summarize what you accomplished."` then deletes chain file.

**Safety:**
- `MAX_CHAIN_TURNS = 10` (30 total tool calls), configurable via `J_MAX_CHAIN_TURNS`.
- Chain terminates on: J declaring complete, empty `next_steps`, max turns reached, or no ACTION in response.
- `.j_chain.json` added to `.gitignore`.

### Why This Kills the Bugs

| Bug | How chain log fixes it |
|-----|----------------------|
| Multi-action dump (Bug #3) | 3-call budget is short enough that J doesn't try to precompute 8 steps |
| Post-compression derailment | No mid-turn compression needed. Clean slate each turn |
| Hallucinated success narratives | J gets re-grounded from chain log each turn. Can't claim steps 4-6 when log only shows 1-3 |
| Ghost edits (`run_str_replace`) | That was compression-induced confusion. 3-call turns with no compression = nothing to confuse |

### Constants (updated)

```
MAX_TOOL_BUDGET    = 3   (default, reverted from Session 29's temporary raise to 6)
CHAIN_LOG_PATH     = .j_chain.json
MAX_CHAIN_TURNS    = 10  (configurable via J_MAX_CHAIN_TURNS, = 30 total tool calls)
PHASE_SIZE         = 4   (preserved but won't trigger at budget=3)
```

### Files Changed

| File | Action | Notes |
|------|--------|-------|
| `app/chat.py` | UPDATED | +148 lines: checkpoint creation, resume loop, chain constants |
| `.gitignore` | UPDATED | Added `.j_chain.json` |

# J — User Manual

> Production guide for the Sovereign Shards developer agent.
> Version: `1.0` · Last updated: 2026-05-05

---

## Table of Contents

1. [The Goal](#the-goal)
2. [What J Can Do Today](#what-j-can-do-today)
3. [What J Cannot Do Yet](#what-j-cannot-do-yet)
4. [Hardware Setup](#hardware-setup)
5. [First Boot](#first-boot)
6. [Configuration](#configuration)
7. [Commands Reference](#commands-reference)
8. [Autonomy Modes](#autonomy-modes)
9. [The Memory System](#the-memory-system)
10. [Example Builds](#example-builds)
11. [Tool Reference](#tool-reference)
12. [Troubleshooting](#troubleshooting)
13. [Architecture Deep Dive](#architecture-deep-dive)

---

## The Goal

Build a **fully local, USB-portable developer agent** with capabilities structurally equivalent to cloud-hosted AI coding tools (Codex, Claude Code, Viktor) — but running entirely on consumer hardware with zero external dependencies.

Specifically:

- **Plan** multi-step engineering tasks from natural language
- **Execute** those tasks using real dev tools (file I/O, shell, git, search, test runners)
- **Verify** each step against success criteria before continuing
- **Remember** context across turns and sessions using tiered memory
- **Self-correct** by detecting errors, reflecting on working memory, and adjusting
- **Run offline** from a 16 GB FAT32 USB stick with no network calls

The framework is complete. The raw language quality — how well J writes code, reasons about architecture, and handles ambiguity — depends entirely on the GGUF model loaded onto the drive. The bigger and better the model, the closer J gets to cloud-tier output.

---

## What J Can Do Today

### Core Agent Loop (Plan → Execute → Verify)
- Parse a natural language goal into concrete steps with dependency ordering
- Execute steps using 10 built-in dev tools
- Verify each step passes its success criteria before proceeding
- Checkpoint progress so interrupted tasks can resume
- Walk task DAGs respecting step dependencies (not just linear lists)

### Developer Tools
| Tool | What It Does |
|------|-------------|
| `run_read` | Read any UTF-8 file |
| `run_write` | Write/overwrite any file |
| `run_str_replace` | Surgical find-and-replace edits |
| `run_bash` | Execute shell commands with timeout |
| `run_exec` | Run arbitrary Python code |
| `run_git` | Full git workflow (status, diff, log, add, commit, branch, checkout, stash, etc.) |
| `run_search` | Regex search across files, respects .gitignore |
| `run_tree` | Recursive directory tree listing |
| `run_test` | Run tests and report pass/fail |
| `run_scaffold` | Quick-create a package directory |

### 3-Tier Memory System
- **Tier 1 — Active Context**: What the model sees right now (reconstructed each turn)
- **Tier 2 — Working Memory**: Rolling JSONL summaries of recent steps, decisions, and errors
- **Tier 3 — Long-Term Memory**: Persistent key-value facts that survive across sessions

### BM25 Retrieval
Before every LLM call, J pulls relevant entries from working memory and long-term memory using BM25 scoring — so the model always sees the most useful context, not just the most recent.

### Weight-Triggered Reflection
When working memory exceeds 32 KB, J automatically asks the model to consolidate entries — compressing N noisy records into a tight set of key decisions, errors, and state. No fixed-interval timer. It fires only when the memory is actually bloated.

### Task Graphs (DAG Execution)
Steps can declare dependencies (`depends_on`). J builds a DAG, sorts it topologically, and executes steps in valid order. Independent steps within a tier can conceptually run in parallel (serial execution currently, but the graph is ready for it).

### Dual Runtime Backend
Works with both `llama.cpp` (server mode) and `Ollama` out of the box. Streaming responses in both cases.

### Preflight Diagnostics
`python run.py --doctor` validates everything before you start: Python deps, model path, server binary, disk space, RAM, server health, drive location, and BUILD_INFO alignment.

### Session Logging
Every conversation is logged to `logs/sessions/` as timestamped text files. Runtime events log to structured JSONL with 512 KB rotation and 5-file limit.

### Five Masters Governance
Code output is evaluated against five heuristic checks (efficiency, error handling, performance, fault tolerance, clarity). Lightweight — no AST parsing yet, but the framework is wired.

### Sandbox Mode
Type `bruce wayne` to toggle sandbox mode — restricts tool execution to read-only operations.

---

## What J Cannot Do Yet

These are the gaps between the current build and full cloud-tier parity:

### 1. Language Quality (Model-Dependent)
The framework is structurally complete, but the *quality of reasoning, code generation, and natural language output* depends on the GGUF model loaded. A 7B-Q5 model will scaffold and edit code reliably. A 14B-Q4 model will handle more complex architecture decisions. Neither will match GPT-4 or Claude 3.5 on nuanced reasoning — that's a model ceiling, not a framework limitation.

**Recommended models (fits 16 GB USB with room for code/logs):**
| Model | Size | Quality | Speed |
|-------|------|---------|-------|
| Qwen2.5-Coder-7B-Q5_K_M | ~5.5 GB | Good for focused tasks | Fast |
| Qwen2.5-Coder-14B-Q4_K_M | ~8.5 GB | Better reasoning | Moderate |
| DeepSeek-Coder-V2-Lite-16B-Q4 | ~9 GB | Strong all-round | Moderate |

### 2. Parallel Step Execution
The task graph supports it (tiers of independent steps), but the executor runs them serially. Wiring parallel execution is straightforward but not yet implemented.

### 3. Streaming Tool Output
Shell commands and test runs capture output after completion. Streaming stdout/stderr back to the user in real-time during long builds would improve the experience.

### 4. Web/API Access (Intentionally Missing)
J is local-first by design. No HTTP calls, no package installs from PyPI during runtime. If you want J to pull a library, pre-install it on the drive.

### 5. Multi-File Refactoring Intelligence
J can edit files individually (str_replace, write), but it doesn't yet have AST-level awareness for cross-file rename, extract-method, or dependency graph analysis. It relies on the LLM's reasoning for multi-file coordination.

### 6. Five Masters — Real AST Analysis
Currently heuristic-based (string matching). A real AST-based evaluator would catch actual antipatterns, cyclomatic complexity, and type issues.

### 7. Self-Healing on Stuck Loops
If the LLM produces invalid tool calls repeatedly, J will retry but doesn't yet have a hard circuit-breaker or fallback strategy.

### 8. Visual/UI Output
No rendering. J works in the terminal. If you want it to produce a web page, it writes the HTML — you open it in a browser yourself.

---

## Hardware Setup

### USB Drive Preparation

1. **Format**: FAT32 (required for cross-platform compatibility and the 4 GB file size limit the code respects)
2. **Label**: Optional but recommended (e.g., `SHARD`)
3. **Structure after setup**:

```
E:\
├── sovereign-shards/          # This repo
│   ├── run.py                 # Entry point
│   ├── .env                   # Your configuration
│   ├── app/                   # Core application
│   ├── tools/                 # Dev tools
│   ├── core/                  # Governance
│   ├── prompts/               # System prompts & templates
│   ├── docs/                  # This manual
│   ├── models/                # ← Put your .gguf file here
│   ├── model-server/          # ← Put llama.cpp binaries here
│   ├── logs/                  # Auto-created
│   └── memory/                # Auto-created
├── python/                    # Embedded Python (optional)
└── Lib/site-packages/         # Pre-installed packages
```

### Installing the Model

1. Download a GGUF model (see recommendations above)
2. Place it at `models/brain.gguf` (or update `LLAMA_MODEL_PATH` in `.env`)
3. That's the single biggest file on the drive

### Installing llama.cpp

1. Download the latest `llama.cpp` release for your platform from [GitHub](https://github.com/ggerganov/llama.cpp/releases)
2. Place `server.exe` (or `llama-server`) in `model-server/`
3. Place `llama.exe` (or `llama-cli`) in `model-server/`
4. Update `.env` if your filenames differ

### Installing Python (Portable)

For a fully portable setup, use [WinPython](https://winpython.github.io/) or [Python embeddable](https://www.python.org/downloads/):

```bash
# From the USB drive root
python -m pip install python-dotenv psutil
```

---

## First Boot

```bash
cd "E:\sovereign-shards"

# Step 1: Verify everything is in place
python run.py --doctor
```

The doctor checks:
- ✅ Python dependencies (`python-dotenv`, `psutil`)
- ✅ Model file exists at configured path
- ✅ Server binary exists
- ✅ Chat template file exists
- ✅ Log directories are writable
- ✅ Disk has ≥1 GB free
- ✅ RAM has ≥2 GB available
- ✅ Server is reachable (if already running)
- ✅ Drive location matches expected root
- ✅ BUILD_INFO aligns with runtime config

Fix any `[FAIL]` items before proceeding.

```bash
# Step 2: Launch
python run.py

# Or with options:
python run.py --mode auto-safe      # Start in auto-safe autonomy
python run.py --message "read run.py and summarize it"  # One-shot mode
```

---

## Configuration

Copy `.env.example` to `.env` and adjust:

```ini
# ── Backend ──────────────────────────────────────
RUNTIME_BACKEND=llama_cpp          # or "ollama"

# ── Server ───────────────────────────────────────
LLAMA_HOST=127.0.0.1
LLAMA_PORT=8080
LLAMA_STARTUP_TIMEOUT=120          # seconds to wait for server

# ── Model ────────────────────────────────────────
LLAMA_MODEL_ALIAS=brain
LLAMA_MODEL_PATH=models\brain.gguf
LLAMA_SERVER_BINARY=model-server\server.exe
LLAMA_CLI_BINARY=model-server\llama.exe

# ── Generation (TUNE THESE) ─────────────────────
OLLAMA_NUM_CTX=4096                # Context window (tokens). 4096-8192 recommended.
OLLAMA_NUM_PREDICT=1024            # Max tokens per response. 512-1024 recommended.
OLLAMA_NUM_THREAD=4                # CPU threads. Match your core count.
OLLAMA_TEMPERATURE=0.1             # Low = precise. 0.0-0.3 for coding.

# ── Sampling ─────────────────────────────────────
LLAMA_TOP_P=0.85
LLAMA_TOP_K=20
LLAMA_MIN_P=0

# ── Hardware ─────────────────────────────────────
REQUIRE_GPU=false                  # Set true if you have GPU + CUDA llama.cpp
```

### Key Tuning Notes

| Parameter | Default | Recommended | Why |
|-----------|---------|-------------|-----|
| `OLLAMA_NUM_CTX` | 1024 | 4096–8192 | More context = J remembers more of the conversation. 1024 is too small for real coding tasks. |
| `OLLAMA_NUM_PREDICT` | 256 | 512–1024 | Longer responses = J can write full functions, not fragments. |
| `OLLAMA_NUM_THREAD` | 2 | Your core count | More threads = faster inference. |
| `OLLAMA_TEMPERATURE` | 0.1 | 0.05–0.2 | Lower = more deterministic code output. |

⚠️ **Important**: Higher `NUM_CTX` uses more RAM. A 14B model with 8192 context can use 12+ GB of RAM. Monitor with `--doctor`.

---

## Commands Reference

| Command | What It Does |
|---------|-------------|
| `/help` | Show all commands |
| `/plan <goal>` | Enter agent mode: plan steps, execute tools, verify results |
| `/tools` | List all registered tools with descriptions |
| `/snapshot` | Print hardware snapshot (CPU, RAM, disk, platform) |
| `/index` | Index the current project directory for context |
| `/mode <level>` | Change autonomy level mid-session |
| `/memory` | Show recent working memory entries and stats |
| `/reflect` | Manually trigger memory compression |
| `build <name>` | Quick-scaffold a Python package directory |
| `bruce wayne` | Toggle sandbox mode (read-only tool restriction) |
| `quit` / `exit` | End the session |

Any other input is treated as a natural conversation message to J.

---

## Autonomy Modes

Control how much J does without asking.

| Mode | Reads | Writes | Exec | Confirmation |
|------|-------|--------|------|-------------|
| `manual` | ✅ | ❌ | ❌ | Every tool call requires approval |
| `semi` | ✅ | Ask | Ask | Side-effects need confirmation |
| `auto-safe` | ✅ | ✅ | ❌ | Reads and writes are automatic; exec blocked |
| `auto-full` | ✅ | ✅ | ✅ | Everything runs automatically |

```bash
# Start in a specific mode
python run.py --mode auto-safe

# Change mid-session
/mode auto-full
```

**Recommendation**: Start with `semi` until you trust J's tool calls, then move to `auto-safe` for normal work. Use `auto-full` only for well-defined batch tasks.

---

## The Memory System

J uses three tiers of memory to maintain context across turns:

```
┌─────────────────────────────────────────┐
│  Tier 1: Active Context                 │  ← What the LLM sees NOW
│  (system prompt + recent messages +     │
│   injected working memory + long-term)  │
├─────────────────────────────────────────┤
│  Tier 2: Working Memory                 │  ← Rolling summaries
│  memory/working_memory.jsonl            │     step / result / issue / decision
│  Compressed each turn. BM25-retrieved.  │     32 KB trigger for reflection.
├─────────────────────────────────────────┤
│  Tier 3: Long-Term Memory              │  ← Persistent facts
│  logs/memory.json                       │     Key-value. 64 KB cap.
│  Survives across sessions.              │     Pruned oldest-first.
└─────────────────────────────────────────┘
```

### How It Works (Every Turn)

1. **Before the LLM call**: `reconstruct_context()` runs:
   - Keeps the system message (persona, tools)
   - BM25-scores working memory entries against the current task → injects top 8
   - BM25-scores long-term memory entries → injects top 5
   - Keeps recent conversation messages
   - Trims everything to fit the context window

2. **After the LLM responds**: `compress_turn()` runs:
   - Heuristically extracts: what the user asked, what J said, any errors, any decisions
   - Appends a one-line JSONL entry to `working_memory.jsonl`

3. **When working memory exceeds 32 KB**: Auto-reflection triggers:
   - Sends all entries to the LLM with a compression prompt
   - LLM consolidates N entries → ~5 tight summaries
   - Atomically replaces the file

This means J never loses important context even in long sessions, and the model always gets a *relevant* window — not just the last N messages.

---

## Example Builds

### Example 1: Scaffold a New Python Project

```
You: /plan Create a Python CLI tool called "linecounter" that recursively
     counts lines of code by file extension, outputs a table, and supports
     --exclude patterns.

J:   [PLAN] 5 step(s):
       ○ step_1: Scaffold the linecounter package directory
       ○ step_2: Implement the core line counting logic (after: step_1)
       ○ step_3: Add CLI argument parsing with argparse (after: step_2)
       ○ step_4: Add --exclude pattern support (after: step_3)
       ○ step_5: Write and run tests (after: step_4)

     [STEP step_1] Scaffold the linecounter package directory
     → run_scaffold linecounter ✓
     → run_write linecounter/__main__.py ✓

     [STEP step_2] Implement the core line counting logic
     → run_write linecounter/counter.py ✓

     ... (continues through all steps) ...

     [DONE] 5/5 steps completed.
```

### Example 2: Debug an Existing Codebase

```
You: /plan The tests in tests/test_auth.py are failing with a KeyError on
     line 42. Find the root cause and fix it.

J:   [PLAN] 4 step(s):
       ○ step_1: Read tests/test_auth.py and identify the failing assertion
       ○ step_2: Read the source file referenced at line 42 (after: step_1)
       ○ step_3: Apply the fix using str_replace (after: step_2)
       ○ step_4: Re-run the tests to verify (after: step_3)

     [STEP step_1] Read tests/test_auth.py...
     → run_read tests/test_auth.py ✓
       Line 42: assert response["user_id"] == expected_id
       The dict doesn't have "user_id" — it's "userId" (camelCase).

     [STEP step_2] Read src/auth.py...
     → run_read src/auth.py ✓
       Confirmed: API returns {"userId": ...} not {"user_id": ...}

     [STEP step_3] Fix the test...
     → run_str_replace {"path": "tests/test_auth.py",
                         "old": "response[\"user_id\"]",
                         "new": "response[\"userId\"]"} ✓

     [STEP step_4] Run tests...
     → run_test python -m pytest tests/test_auth.py ✓
       All 7 tests passed.

     [DONE] 4/4 steps completed.
```

### Example 3: Interactive Coding Session

```
You: Write me a FastAPI endpoint that accepts a JSON payload with a
     "message" field and returns it reversed.

J:   Certainly. Here's a minimal endpoint:

     ```python
     from fastapi import FastAPI
     from pydantic import BaseModel

     app = FastAPI()

     class Payload(BaseModel):
         message: str

     @app.post("/reverse")
     def reverse_message(payload: Payload):
         return {"reversed": payload.message[::-1]}
     ```

     Run it with `uvicorn main:app`. Send a POST to `/reverse`
     with `{"message": "hello"}` and you'll get `{"reversed": "olleh"}`.

You: Write that to api/main.py

J:   → run_write api/main.py ✓
     Done. File written at api/main.py.
```

### Example 4: Git Workflow

```
You: /plan Create a feature branch called "add-logging", add Python logging
     to all modules in src/, commit with a descriptive message.

J:   [PLAN] 4 step(s):
       ○ step_1: Create and checkout the feature branch
       ○ step_2: List all Python files in src/ (after: step_1)
       ○ step_3: Add logging imports and setup to each module (after: step_2)
       ○ step_4: Stage and commit all changes (after: step_3)

     ... (executes using run_git and run_str_replace) ...

     [DONE] Committed on branch "add-logging":
     "feat: add structured logging to all src/ modules"
```

### Example 5: Explore and Index an Unfamiliar Project

```
You: /index

J:   Indexing project at E:\sovereign-shards...
     29 Python files found.
     Key modules: app/chat.py (main loop), app/agent/ (brain),
     tools/run/ (dev tools), core/ (governance).

You: /memory

J:   [WORKING MEMORY — recent steps]
     • Indexed project: 29 files, 3089 lines across app/, tools/, core/
       → Decided: main entry is run.py, chat loop is app/chat.py
     [1,247 bytes — reflection not needed]

You: What does the Five Masters system do?

J:   The Five Masters system (core/fivemasters.py) evaluates generated code
     against five quality heuristics, each named after a programming legend:
     ...
```

---

## Tool Reference

Tools live in `tools/run/` and auto-register via `registry.json`. Each tool declares its arguments and side-effect type.

### run_read
Read a UTF-8 text file and return its contents.
```
Args: path
Side-effect: read
```

### run_write
Write content to a file (creates or overwrites).
```
Args: path, content
Side-effect: write
```

### run_str_replace
Surgical find-and-replace in a file. Fails if the old string isn't found (prevents blind edits).
```
Args: json_payload ({"path": "...", "old": "...", "new": "..."})
Side-effect: write
```

### run_bash
Execute a shell command with optional timeout.
```
Args: command
Side-effect: exec
Default timeout: 30 seconds
```

### run_exec
Execute Python code in a subprocess.
```
Args: code
Side-effect: exec
```

### run_git
Git operations. Allowed subcommands: `status`, `diff`, `log`, `add`, `commit`, `branch`, `checkout`, `stash`, `show`, `reset`, `rev-parse`, `remote`.
```
Args: subcommand, ...args
Side-effect: exec
```

### run_search
Regex search across files. Respects `.gitignore`. Supports `--ext` filter.
```
Args: pattern, [path], [--ext .py]
Side-effect: read
```

### run_tree
Recursive directory tree listing.
```
Args: [path], [--depth N]
Side-effect: read
Default depth: 4
```

### run_test
Run a test command and report pass/fail.
```
Args: command
Side-effect: exec
```

### run_scaffold
Create a package directory with `__init__.py`.
```
Args: name
Side-effect: write
```

---

## Troubleshooting

### "Model file not found"
- Check `LLAMA_MODEL_PATH` in `.env`
- Default: `models/brain.gguf`
- Run `python run.py --doctor` to see the resolved path

### "Server binary not found"
- Check `LLAMA_SERVER_BINARY` in `.env`
- Default: `model-server/server.exe`
- Download from [llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases)

### Slow generation
- Increase `OLLAMA_NUM_THREAD` to match your CPU core count
- Use a smaller quantization (Q4 instead of Q5)
- Consider a smaller model (7B instead of 14B)
- Close other programs to free RAM

### "Context window too small" / truncated responses
- Increase `OLLAMA_NUM_CTX` to 4096 or 8192
- Increase `OLLAMA_NUM_PREDICT` to 1024
- Monitor RAM usage — larger context = more memory

### Working memory keeps triggering reflection
- This is normal in long sessions
- The 32 KB threshold is in `app/agent/working_memory.py` (`MAX_WM_BYTES`)
- You can adjust it if needed

### FAT32 file size issues
- All writes are atomic (`.tmp` → rename)
- Log files rotate at 512 KB with 5-file limit
- No single file approaches the 4 GB FAT32 limit

### Drive letter changed
- Update `SHARD_EXPECTED_ROOT` in `.env` (cosmetic — affects `--doctor` only)
- All paths in `.env` are relative to the repo root

---

## Architecture Deep Dive

### The Agent Loop

```
User message
     │
     ▼
reconstruct_context()        ← Pull relevant memory (BM25)
     │
     ▼
LLM generates response       ← Streaming via llama.cpp or Ollama
     │
     ├── Tool call detected? ──→ Parse → Confirm (if semi) → Execute → Log
     │                                                           │
     │                                                           ▼
     │                                                    Append to messages
     │                                                    Loop back to LLM
     │
     ▼
compress_turn()              ← Heuristic summary → working_memory.jsonl
     │
     ▼
needs_reflection()?          ← If > 32 KB: auto-consolidate
     │
     ▼
Done. Wait for next message.
```

### Task Graph Execution (/plan mode)

```
/plan "goal"
     │
     ▼
build_plan_prompt()          ← Sends goal to LLM
     │
     ▼
parse_plan()                 ← Extracts steps with depends_on
     │
     ▼
topo_tiers()                 ← Kahn's algorithm → execution tiers
     │
     ▼
for each tier:
  for each ready step:
    build_step_prompt()      ← Focus LLM on one step
    LLM responds
    extract tool calls
    execute via registry
    build_verify_prompt()    ← Ask: did it pass criteria?
    parse_verdict()
    checkpoint (task_store)
```

### File Layout

```
sovereign-shards/
├── run.py                          # CLI entry point
├── .env.example                    # Configuration template
├── requirements.txt                # python-dotenv, psutil
├── app/
│   ├── __init__.py
│   ├── chat.py                     # Main loop, command dispatch, agent wiring
│   ├── client.py                   # RuntimeConfig from .env
│   ├── doctor.py                   # Preflight diagnostics
│   ├── errors.py                   # Typed error taxonomy
│   ├── file_tools.py               # FAT32-safe file I/O
│   ├── local_server.py             # llama.cpp server lifecycle
│   ├── runtime_log.py              # JSONL structured logging
│   ├── session.py                  # Conversation transcript logging
│   ├── system_tools.py             # Hardware snapshot (CPU, RAM, disk)
│   └── agent/
│       ├── __init__.py
│       ├── contracts.py            # AgentStep, ToolCall, ToolResult, AgentTask
│       ├── context.py              # trim_context, reconstruct_context
│       ├── executor.py             # Tool execution engine
│       ├── graph.py                # DAG task graph (Kahn's topo-sort)
│       ├── indexer.py              # Project directory indexer
│       ├── memory.py               # Tier 3: long-term key-value memory
│       ├── planner.py              # LLM → AgentStep[] with dependencies
│       ├── reflection.py           # Weight-triggered memory compression
│       ├── retriever.py            # BM25 scorer (pure Python)
│       ├── task_store.py           # Checkpoint/resume for agent tasks
│       ├── tool_registry.py        # Auto-discovery + schema validation
│       ├── verifier.py             # Step success/fail verdict parser
│       └── working_memory.py       # Tier 2: rolling JSONL summaries
├── core/
│   └── fivemasters.py              # Code quality heuristics
├── tools/run/
│   ├── registry.json               # Tool definitions (auto-loaded)
│   ├── bash.py, exec.py, git.py    # Execution tools
│   ├── read.py, write.py           # File I/O tools
│   ├── str_replace.py              # Surgical edit tool
│   ├── search.py, tree.py          # Discovery tools
│   ├── test.py                     # Test runner
│   └── scaffold.py                 # Package scaffolder
├── prompts/
│   ├── J-system.txt                # System persona
│   └── J-chat-template.jinja       # Chat format template
├── docs/
│   └── USER_MANUAL.md              # This file
├── models/                         # .gguf files (gitignored)
├── model-server/                   # llama.cpp binaries (gitignored)
├── logs/                           # Auto-created runtime logs
└── memory/                         # Auto-created working memory
```

---

*Built local. Runs local. Stays local.*

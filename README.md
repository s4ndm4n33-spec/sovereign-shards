<p align="center">
  <img src="https://img.shields.io/badge/status-production--ready-brightgreen?style=for-the-badge" alt="Status: Production Ready" />
  <img src="https://img.shields.io/badge/runs_on-USB_drive-blue?style=for-the-badge" alt="Runs on USB" />
  <img src="https://img.shields.io/badge/cloud-none-critical?style=for-the-badge" alt="No Cloud" />
  <img src="https://img.shields.io/badge/deps-2-yellow?style=for-the-badge" alt="2 Dependencies" />
</p>

<h1 align="center">Sovereign Shards — J</h1>

<p align="center">
  <strong>A fully local AI developer agent that runs from a USB stick.</strong><br/>
  No cloud. No API keys. No internet. Plug in and build.
</p>

---

## What Is J?

J is a **self-contained, autonomous developer agent** — not a chatbot. It plans multi-step tasks, writes code, runs tests, manages git, analyzes codebases, and self-corrects — all powered by a local GGUF language model running entirely on your hardware.

```
You  ──→  J  ──→  Plan (DAG)  ──→  Execute (14 tools)  ──→  Verify
                     ↕                    ↕                      ↕
               Working Memory       Tool Registry          Task Checkpoint
                     ↕                    ↕                      ↕
              Long-Term Memory     Streaming Output        Circuit Breaker
```

Think of it as **Codex or Claude Code, but it runs off a Kingston USB stick** in your pocket.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🧠 **Plan → Execute → Verify** | DAG-based task planner with dependency resolution, parallel execution, and automatic verification |
| 🔧 **14+ Built-In Dev Tools** | File editing, bash, git, search, tree, test, SQL, integrity hashing — all auto-discovered |
| 💾 **3-Tier Memory System** | Active context reconstruction + rolling working memory + persistent long-term memory with BM25 retrieval |
| 🔍 **AST Code Intelligence** | Multi-file refactoring analysis — dead code, circular imports, unused imports, symbol shadows, rename helpers |
| ⚡ **Parallel Execution** | Thread-pool tier runner for independent task steps — respects dependency order, runs the rest concurrently |
| 🛡️ **Self-Healing Circuit Breaker** | Detects stuck loops, repeat errors, and runaway turns — auto-recovers or gracefully exits |
| 📡 **Streaming Output** | Real-time line-by-line tool output — see builds, tests, and processes as they happen |
| 🏛️ **Five Masters Code Review** | AST-powered analysis inspired by Korotkevich, Torvalds, Carmack, Hamilton, and Ritchie |
| 🧪 **Pre-Push Sandbox** | Copies project to temp dir, runs a 5-check validation gauntlet — nothing broken leaves the drive |
| 📊 **Visual Reports** | Terminal-native progress bars, task trees, and standalone HTML reports (dark theme, zero deps) |
| 🔨 **Inference Tool Forge** | "Build a tool for X" → J researches the domain, generates code, validates in sandbox, and hot-registers the new tool — mid-session, no restart |
| 🧪 **127-Test Suite** | Full `unittest` coverage: memory, retriever, planner, executor, sandbox, forge, circuit breaker — runs anywhere with zero test deps |
| 🔒 **Fully Offline** | Zero network calls. Zero telemetry. Your code never leaves your machine |

---

## 🚀 Quick Start

```bash
# 1. Plug in your USB drive (e.g., E:\)
cd "E:\sovereign-shards"

# 2. Install the two dependencies
pip install python-dotenv psutil

# 3. Drop a GGUF model into the models/ folder
#    (Recommended: Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf)

# 4. Run the preflight check
python run.py --doctor

# 5. Launch
python run.py
```

That's it. J starts the local model server, loads the brain, and drops you into an interactive session.

> 📘 See **[docs/USER_MANUAL.md](docs/USER_MANUAL.md)** for the full production guide with 5 example builds, configuration tuning, and architecture deep dives.

---

## 🏗️ Architecture

```
sovereign-shards/
├── run.py                     # Entry point
├── app/
│   ├── chat.py                # Interactive session, command dispatch
│   ├── client.py              # Dual backend (llama.cpp + Ollama)
│   ├── local_server.py        # Server lifecycle management
│   ├── doctor.py              # Preflight hardware diagnostics
│   ├── errors.py              # Typed error taxonomy
│   ├── runtime_log.py         # Structured JSONL logging
│   ├── session.py             # Session transcript management
│   ├── system_tools.py        # Hardware identity + USB detection
│   └── agent/
│       ├── planner.py         # LLM-driven task decomposition + forge gate
│       ├── executor.py        # Tool dispatch + result capture
│       ├── verifier.py        # Outcome validation
│       ├── graph.py           # Kahn's algorithm DAG execution
│       ├── parallel.py        # ThreadPool tier runner (3 workers)
│       ├── context.py         # Active context reconstruction
│       ├── working_memory.py  # JSONL rolling memory (32KB threshold)
│       ├── memory.py          # Long-term persistent memory (64KB cap)
│       ├── retriever.py       # Pure-Python BM25 retrieval (~97 lines)
│       ├── reflection.py      # Weight-triggered memory compression
│       ├── contracts.py       # Typed dataclasses + autonomy modes
│       ├── task_store.py      # Checkpoint store with depends_on
│       ├── indexer.py         # Project file indexer
│       ├── streaming.py       # Real-time subprocess output
│       ├── refactor.py        # Multi-file AST analysis engine
│       ├── circuit_breaker.py # Stuck-loop detection + recovery
│       ├── visual.py          # Terminal UI + HTML report generation
│       ├── sandbox.py         # Pre-push validation sandbox
│       ├── tool_registry.py   # Auto-discovery + schema extraction
│       ├── tool_researcher.py # Intent detection + domain decomposition
│       ├── tool_forge.py      # Code gen + sandbox validation + hot-register
│       └── tool_template.py   # Canonical tool contract reference
├── core/
│   └── fivemasters.py         # AST code quality (5 analysis masters)
├── tests/                     # 127-test suite (unittest, zero deps)
├── tools/run/                 # 10+ auto-discovered tool scripts
│   ├── str_replace.py         # Surgical file editing
│   ├── bash.py                # Streaming shell execution
│   ├── git.py                 # Git ops (sandbox-gated push)
│   ├── search.py              # Regex search across files
│   ├── tree.py                # Directory tree visualization
│   ├── test.py                # Test runner with result parsing
│   ├── sql.py                 # SQLite (WAL mode, FAT32-safe)
│   ├── integrity.py           # SHA-256 file hashing + baselines
│   ├── read.py                # File reading with line ranges
│   └── write.py               # Atomic file writes (.tmp→rename)
├── models/                    # Drop your .gguf file here
├── logs/                      # Auto-rotated session + runtime logs
└── docs/
    └── USER_MANUAL.md         # Full production guide (~700 lines)
```

---

## 🧠 The Memory System

J doesn't use a growing conversation that eventually overflows. Instead, it reconstructs a *fresh, minimal context* every turn:

| Tier | What | Storage | Lifecycle |
|------|------|---------|-----------|
| **Active Context** | What the model sees *right now* | ~2-4 KB (ephemeral) | Rebuilt every turn from tiers below |
| **Working Memory** | Rolling compressed summaries | JSONL, self-prunes at 32 KB | Weight-triggered reflection compresses automatically |
| **Long-Term Memory** | Persistent facts, patterns, preferences | JSON, hard-capped at 64 KB | Survives across sessions |

**BM25 retrieval** scores all memory entries against the current task and pulls only what's relevant — no embeddings, no vectors, no external service. Pure term-frequency math in ~97 lines of Python.

> At heavy daily use (80 sessions/month), total disk growth is **~10-12 MB/month**. The 16 GB USB has capacity for ~52 years of memory.

---

## 🧪 Pre-Push Sandbox

Before any `git push` or `git commit`, J automatically validates the entire project:

```
┌─────────────────────────────────────────────┐
│  1. ✅ Conflict Check    — merge markers     │
│  2. ✅ Syntax            — py_compile all    │
│  3. ✅ AST Parse         — structural check  │
│  4. ✅ Tests             — auto-detect suite │
│  5. ✅ Five Masters      — code quality      │
│                                              │
│  🟢 SAFE TO PUSH                             │
└─────────────────────────────────────────────┘
```

Failed checks **block the operation**. No broken code leaves the drive.

---

## 🎯 Recommended Model

| Model | Size | Why |
|-------|------|-----|
| **Qwen2.5-Coder-14B-Instruct Q4_K_M** | ~8.5 GB | Purpose-built for code, strong tool use, 32K context, best quality-to-size ratio |
| Qwen2.5-Coder-7B Q5_K_M | ~5.5 GB | Lighter alternative, faster inference |
| DeepSeek-Coder-V2-Lite-16B Q4_K_M | ~9 GB | Competitive code quality |

> Download the `.gguf` from [HuggingFace](https://huggingface.co) and drop it in `models/`. J auto-detects it on launch.

---

## 💻 Hardware Requirements

| Spec | Minimum | Recommended |
|------|---------|-------------|
| **Drive** | 16 GB USB 2.0, FAT32 | Same |
| **RAM** | 8 GB | 16 GB |
| **CPU** | 4 cores | 8+ cores |
| **GPU** | Not required | 6+ GB VRAM (optional, faster inference) |
| **OS** | Windows 10+ / Linux / macOS | Any with Python 3.10+ |
| **Python** | 3.10+ | 3.12+ |

---

## 📋 Commands

| Command | What It Does |
|---------|--------------|
| `/plan <goal>` | Decompose a goal into a DAG of executable steps |
| `/tools` | List all registered tools and their descriptions |
| `/memory` | Show working + long-term memory stats |
| `/reflect` | Force memory compression and pruning |
| `/refactor` | Run AST analysis on the project (generates HTML report) |
| `/sandbox` | Run pre-push validation gauntlet manually |
| `/report` | Generate visual HTML task report |
| `/integrity` | SHA-256 hash all project files |
| `/index` | Re-index the project file tree |
| `/snapshot` | Save session state |
| `/help` | Show all commands |

---

## 📦 Dependencies

```
python-dotenv
psutil
```

That's it. Two packages. Everything else is Python standard library.

---

## 📊 Project Stats

```
61 Python files  ·  7,096 lines of code  ·  2 dependencies  ·  14+ tools (more forged at runtime)
127 tests  ·  Zero network calls  ·  Zero telemetry  ·  100% local
```

---

## 🗺️ Roadmap

- [x] ~~**Inference Tool Forge**~~ — "Figure out how to make STL files" → J researches the domain, generates tool code, validates in sandbox, and hot-registers — *shipped*
- [x] ~~**Test Suite**~~ — 127 tests covering all subsystems — *shipped*
- [ ] **Workflow Abstraction** — Extract reusable `Workflow` class from forge + task pipelines
- [ ] **Multi-Language Support** — Extend beyond Python (JS, Rust, Go)
- [ ] **Voice Interface** — Local speech-to-text for hands-free coding (British English)

---

<p align="center">
  <strong>Built to run where you are. No cloud required.</strong><br/>
  <sub>Sovereign Shards — because your code belongs to you.</sub>
</p>

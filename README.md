<p align="center">
  <img src="assets/icon.png" alt="Sovereign Shards" width="120" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-v1.0--rc-brightgreen?style=for-the-badge" alt="Status: v1.0 RC" />
  <img src="https://img.shields.io/badge/runs_on-USB_drive-blue?style=for-the-badge" alt="Runs on USB" />
  <img src="https://img.shields.io/badge/cloud-none-critical?style=for-the-badge" alt="No Cloud" />
  <img src="https://img.shields.io/badge/deps-2-yellow?style=for-the-badge" alt="2 Dependencies" />
  <img src="https://img.shields.io/badge/tests-147%2B_passing-success?style=for-the-badge" alt="147+ Tests" />
</p>

<h1 align="center">Sovereign Shards — J</h1>

<p align="center">
  <strong>A fully local AI developer agent that runs from a USB stick.</strong><br/>
  No cloud. No API keys. No internet. Plug in and build.
</p>

<p align="center">
  <a href="https://sovereign-shards-62eaaf99.viktor.space">Landing Page</a> · 
  <a href="https://five-masters-b9b95dc3.viktor.space">The Five Masters</a> · 
  <a href="docs/USER_MANUAL.md">User Manual</a> · 
  <a href="docs/ROADMAP.md">Roadmap</a>
</p>

---

## What Is J?

J is a **self-contained, autonomous developer agent** — not a chatbot. It decomposes tasks into dependency graphs, calls tools, verifies results, and self-corrects. The language model is the language engine. The framework is the reasoning layer.

```
User Input
    │
    ▼
┌──────────┐  match?   ┌──────────┐
│  Router   │─────────▶│  Tool    │──▶ Result
│  (zero    │  yes      │  Execute │
│  inference│           └──────────┘
│  cost)    │
└────┬─────┘
     │ no match
     ▼
┌────────────────────────────┐
│  Context Reconstruction    │
│  System + BM25 Memory +   │
│  Conversation (trimmed)    │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│  LLM (local GGUF model)   │
│  → ACTION:{tool, args}    │
│  → Verify → Loop or Done  │
└────────────────────────────┘
```

Think of it as **Codex or Claude Code, but it runs off a Kingston USB stick** in your pocket.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🧠 **Plan → Execute → Verify** | DAG-based task planner with dependency resolution, parallel execution, and automatic verification |
| ⚡ **Fast Command Router** | Regex/keyword dispatcher handles shell, file, and code operations at zero inference cost — model only called when language understanding is needed |
| 🔧 **18+ Built-In Dev Tools** | File editing, bash, git, search, tree, test, SQL, integrity hashing — all auto-discovered from `tools/run/` |
| 🔨 **Inference Tool Forge** | "Build a tool for X" → J researches the domain, generates code, validates in sandbox, and hot-registers the new tool mid-session |
| 💾 **3-Tier Memory System** | Active context reconstruction + rolling working memory + persistent long-term memory with BM25 retrieval |
| 🏛️ **The Five Masters** | AST-powered code governance — 5 engineering dimensions, 8 deterministic transforms, zero inference cost detection |
| 🔬 **Code Optimizer** | `/optimize` command: analyse code against the Five Masters, apply deterministic fixes, then optional LLM-assisted semantic rewrites — the first product feature |
| 🛡️ **Pre-Push Sandbox** | 5-check validation gauntlet (conflicts, syntax, AST, tests, Five Masters) — nothing broken leaves the drive |
| 🔄 **Self-Healing Circuit Breaker** | Detects stuck loops, repeat errors, and runaway turns — auto-recovers or gracefully exits |
| 📡 **Streaming Output** | Real-time line-by-line tool output — see builds, tests, and processes as they happen |
| 🧪 **147+ Test Suite** | Full `unittest` coverage: memory, retriever, planner, executor, sandbox, forge, circuit breaker, optimizer — runs anywhere with zero test deps |
| 🔒 **Fully Offline** | Zero network calls. Zero telemetry. Your code never leaves your machine |

---

## 🚀 Quick Start

### USB Drive (Recommended)

```
1. Plug in your USB drive (e.g., E:\)
2. Open Command Prompt (not PowerShell, not Git Bash)
3. E:
4. cd "dev shard"
5. run-shard.bat
```

J starts the local model server, loads the brain, and drops you into an interactive session.

> ⚠️ Always use `run-shard.bat` from Command Prompt. Windows associates `.py` files with VS Code — running `run.py` directly opens the editor instead of executing.

### Development Machine

```bash
git clone https://github.com/s4ndm4n33-spec/sovereign-shards.git
cd sovereign-shards
pip install python-dotenv psutil
cp .env.example .env            # Edit for your hardware
python run.py --doctor           # Preflight check
python run.py                    # Launch
```

> 📘 See **[docs/USER_MANUAL.md](docs/USER_MANUAL.md)** for the full guide with example builds, configuration tuning, and architecture deep dives.

---

## 🏛️ The Five Masters

The engineering philosophy that governs all code quality decisions. Not a linter — a transformer.

| Master | Domain | What They Enforce |
|--------|--------|-------------------|
| **Korotkevich** | Efficiency | No `range(len())`. No `list(filter())`. No repeated dict lookups in loops. Prefer generators. |
| **Torvalds** | Error Handling | No bare `except:`. No swallowed exceptions. Every error handled with intent. |
| **Carmack** | Performance | No nested loops beyond O(n²). No string concat in loops. Flag excessive nesting. |
| **Hamilton** | Fault Tolerance | Every non-trivial function has a failure return path. Defensive coding. No silent failures. |
| **Ritchie** | Clarity | `snake_case` functions, `PascalCase` classes. All call sites updated on rename. Dunders and privates exempt. |

**Detection** is pure AST — zero inference cost.  
**Transforms** are deterministic — 8 AST rewrites that produce valid Python every time.  
**The optimizer** chains it all: analyse → plan → transform → verify.

```
/optimize app/chat.py              # Analyse and fix one file
/optimize app/ --dry-run           # Preview all changes in a directory
/optimize app/ --no-model --diff   # Deterministic fixes only, show diffs
```

> 🏛️ **[Read the Code Commandments →](https://five-masters-b9b95dc3.viktor.space)**

---

## 🧠 The Memory System

J doesn't use a growing conversation that eventually overflows. It reconstructs a *fresh, minimal context* every turn:

| Tier | What | Storage | Lifecycle |
|------|------|---------|-----------|
| **Active Context** | What the model sees *right now* | Ephemeral | Rebuilt every turn from tiers below |
| **Working Memory** | Rolling compressed summaries | JSONL (auto-prunes at 32 KB) | Weight-triggered reflection compresses automatically |
| **Long-Term Memory** | Persistent facts and preferences | JSON (64 KB cap) | Survives across sessions indefinitely |

**BM25 retrieval** scores all memory entries against the current task and pulls only what's relevant — no embeddings, no vectors, no external service. Pure term-frequency math in ~97 lines of Python.

**Pre-flight budget gate** enforces a hard context ceiling with 3-stage escalation trimming. The system prompt is always protected. Identity never gets trimmed away.

---

## 🏗️ Architecture

```
sovereign-shards/
├── run.py                      # Entry point — args, modes, diagnostics
├── run-shard.bat               # Windows USB one-click launcher
├── app/
│   ├── chat.py                 # Main chat loop (891 lines)
│   ├── client.py               # RuntimeConfig — provider-agnostic backend
│   ├── local_server.py         # llama.cpp server lifecycle management
│   ├── router.py               # Fast command router (zero inference cost)
│   ├── doctor.py               # Preflight hardware diagnostics
│   └── agent/
│       ├── context.py          # 3-stage context budget gate + step seaming
│       ├── working_memory.py   # Tier 2: append-only JSONL summaries
│       ├── memory.py           # Tier 3: persistent key-value store
│       ├── retriever.py        # BM25 retrieval (~97 lines)
│       ├── reflection.py       # Weight-triggered memory compression
│       ├── planner.py          # Task decomposition → DAG
│       ├── executor.py         # Tool dispatch + result capture
│       ├── graph.py            # Kahn's algorithm DAG execution
│       ├── parallel.py         # ThreadPool for independent steps
│       ├── optimizer.py        # Five Masters code optimizer pipeline
│       ├── transforms.py       # 8 deterministic AST transforms
│       ├── sandbox.py          # Pre-push validation gauntlet
│       ├── tool_registry.py    # Auto-discovery + schema extraction
│       ├── tool_forge.py       # Runtime tool generation
│       ├── circuit_breaker.py  # Stuck-loop detection + recovery
│       └── refactor.py         # Multi-file AST analysis engine
├── core/
│   └── fivemasters.py          # Five Masters AST governance (5 visitors)
├── prompts/
│   ├── J-system.txt            # System prompt (~130 tokens — lean)
│   └── J-chat-template.jinja   # ChatML template for llama.cpp
├── tools/run/                  # 18+ auto-discovered tool scripts
├── tests/                      # 147+ tests (unittest, zero deps)
├── models/                     # GGUF model files (gitignored)
├── memory/                     # Runtime memory (gitignored)
└── docs/
    ├── USER_MANUAL.md          # Full user guide
    ├── ROADMAP.md              # 5-phase roadmap with phase gates
    ├── MIGRATION_LOG.md        # Architecture + handoff document
    ├── CODE_OPTIMIZER_SPEC.md  # Optimizer technical specification
    ├── BUSINESS_MODEL.md       # Three-tier business model
    └── TEST_PLAN.md            # Test strategy and coverage
```

---

## 🎯 Recommended Models

| Model | GGUF Size | RAM Usage | Best For |
|-------|-----------|-----------|----------|
| **Qwen2.5-Coder-7B-Instruct Q4_K_M** | ~4.5 GB | ~6–8 GB | ✅ 16 GB systems (recommended) |
| Qwen2.5-Coder-14B-Instruct Q4_K_M | ~8.5 GB | ~12–15 GB | 32 GB+ systems only |
| DeepSeek-Coder-V2-Lite-16B Q4_K_M | ~9 GB | ~13–16 GB | 32 GB+ systems only |

> **FAT32 note:** Files over 4 GB must be split. Use `llama-gguf-split --split-max-size 3G model.gguf J` to create shards. Point `LLAMA_MODEL_PATH` at the first shard — llama.cpp auto-loads the rest.

Download `.gguf` files from [HuggingFace](https://huggingface.co) and place them in `models/`.

---

## 💻 Hardware Requirements

| Spec | Minimum | Recommended |
|------|---------|-------------|
| **Drive** | 16 GB USB 2.0, FAT32 | 32 GB+ USB 3.0 |
| **RAM** | 8 GB (with 7B model) | 16 GB |
| **CPU** | 2 cores | 4+ cores |
| **GPU** | Not required | Vulkan-compatible (optional, faster inference) |
| **OS** | Windows 10+ / Linux / macOS | Windows 10+ (primary target) |
| **Python** | 3.10+ (embedded on USB) | 3.12+ |

> J carries its own embedded Python on the USB drive. It never calls the host system's Python.

---

## 📋 Commands

| Command | What It Does |
|---------|--------------|
| `/plan <goal>` | Decompose a goal into a DAG of executable steps |
| `/optimize <path>` | Run the Five Masters code optimizer (supports `--dry-run`, `--no-model`, `--diff`) |
| `/tools` | List all registered tools |
| `/memory` | Show working + long-term memory stats |
| `/reflect` | Force memory compression |
| `/sandbox` | Run pre-push validation gauntlet |
| `/model <name>` | Hot-swap the active model mid-session |
| `/refactor` | Multi-file AST analysis (generates HTML report) |
| `/integrity` | SHA-256 hash all project files |
| `run.py --doctor` | Preflight diagnostics (checks model, server, RAM, config) |
| `/help` | Show all commands |

---

## 📦 Dependencies

```
python-dotenv
psutil
```

Two packages. Everything else is Python standard library. That's a hard constraint.

---

## 📊 Project Stats

```
91 files  ·  63 Python modules  ·  2 dependencies  ·  18+ tools
147+ tests  ·  8 AST transforms  ·  5 code quality masters
Zero network calls  ·  Zero telemetry  ·  100% local
```

---

## 🗺️ Roadmap

Five phases from prototype to product. Each has a gate — every criterion must pass before moving on.

| Phase | Version | Focus |
|-------|---------|-------|
| **1. Stabilize** | v1.0 | Model swap to 7B, boot validation, 20-turn smoke test |
| **2. Harden** | v1.0.1 | First-run experience, error clarity, 50-turn identity stress test |
| **3. Optimize** | v1.1 | Multi-file optimizer, model hot-swap, tool forge validation |
| **4. Extend** | v1.5 | Codebase Forge, voice interface (British English), multi-language AST |
| **5. Scale** | v2.0 | Plug-and-play shards, multi-shard protocol, enterprise packaging |

> 📋 **[Full roadmap with step-by-step instructions →](docs/ROADMAP.md)**

---

## 💼 Business Model

| Tier | What | Price |
|------|------|-------|
| **Open Source Core** | This repo. Full framework, all tools, all tests. | Free |
| **Pre-Loaded Shards** | USB drives with model, Python, server — plug and play. | $79–$149 |
| **Enterprise** | Custom shards, dedicated support, compliance packaging. | $500–$5K+ |

> 📋 **[Full business model →](docs/BUSINESS_MODEL.md)**

---

## 📚 Documentation

| Document | What It Covers |
|----------|----------------|
| [User Manual](docs/USER_MANUAL.md) | Commands, configuration, example workflows |
| [Roadmap](docs/ROADMAP.md) | 5-phase plan with success criteria and phase gates |
| [Migration Log](docs/MIGRATION_LOG.md) | Architecture, standards, constraints, known bugs, design rationale |
| [Code Optimizer Spec](docs/CODE_OPTIMIZER_SPEC.md) | Five Masters optimizer technical specification |
| [Test Plan](docs/TEST_PLAN.md) | Test strategy, coverage map, how to run |
| [Business Model](docs/BUSINESS_MODEL.md) | Three-tier pricing and distribution strategy |

---

<p align="center">
  <strong>Built to run where you are. No cloud required.</strong><br/>
  <sub>Sovereign Shards — because your code belongs to you.</sub>
</p>

<p align="center">
  <em>"Systems that persist."</em>
</p>

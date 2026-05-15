<p align="center">
  <video src="https://github.com/s4ndm4n33-spec/sovereign-shards/raw/main/assets/j-demo.mp4" width="100%" autoplay muted loop playsinline>
    Your browser does not support the video tag. <a href="assets/j-demo.mp4">Watch the demo →</a>
  </video>
</p>

<p align="center">
  <em>80 seconds. Everything J does. No cloud, no API keys, no internet.</em>
</p>

<p align="center">
  <img src="assets/icon.png" alt="Sovereign Shards" width="120" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/phase_1-CLEARED-brightgreen?style=for-the-badge" alt="Phase 1: Cleared" />
  <img src="https://img.shields.io/badge/runs_on-USB_drive-blue?style=for-the-badge" alt="Runs on USB" />
  <img src="https://img.shields.io/badge/cloud-none-critical?style=for-the-badge" alt="No Cloud" />
  <img src="https://img.shields.io/badge/deps-2-yellow?style=for-the-badge" alt="2 Dependencies" />
  <img src="https://img.shields.io/badge/tests-147%2B_passing-success?style=for-the-badge" alt="147+ Tests" />
  <img src="https://img.shields.io/badge/security-defence_suite-blueviolet?style=for-the-badge" alt="Defence Suite" />
</p>

<h1 align="center">Sovereign Shards — J</h1>

<p align="center">
  <strong>A fully local AI developer agent that runs from a USB stick.</strong><br/>
  No cloud. No API keys. No internet. Two dependencies. Plug in and build.
</p>

<p align="center">
  <a href="https://sovereign-shards-62eaaf99.viktor.space">Landing Page</a> · 
  <a href="https://five-masters-b9b95dc3.viktor.space">The Five Masters</a> · 
  <a href="docs/USER_MANUAL.md">User Manual</a> · 
  <a href="docs/ROADMAP.md">Roadmap</a> · 
  <a href="docs/NEXT_10_STEPS.md">Next 10 Steps</a> · 
  <a href="CONTRIBUTING.md">Contributing</a>
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

Think of it as **Codex or Claude Code, but it runs off a Kingston USB stick** in your pocket. No cloud account. No API key. No internet connection. Just your hardware.

**Why this matters:** Every other autonomous coding agent (Claude Code, Codex, Cline, Aider) requires cloud APIs, internet, or heavy toolchains. J requires a USB port and 16 GB of RAM. The agent that runs in your pocket is the agent that runs anywhere.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🧠 **Plan → Execute → Verify** | DAG-based task planner with dependency resolution, parallel execution, and automatic verification |
| ⚡ **Fast Command Router** | Regex/keyword dispatcher handles shell, file, and code operations at zero inference cost — model only called when language understanding is needed |
| 🔧 **17 Built-In Dev Tools** | File editing, bash, git, search, tree, test, SQL, integrity hashing, codebase stats, calculator — all auto-discovered from `tools/run/` |
| 🛡️ **Defence Suite** | Three-layer security toolkit: SHIELD (shard self-defence), SCAN (host security audit), BRIDGE (remediation). Portable air-gapped security auditor |
| 🔨 **Inference Tool Forge** | "Build a tool for X" → J researches the domain, generates code, validates in sandbox, and hot-registers the new tool mid-session |
| 💾 **3-Tier Memory System** | Active context reconstruction + rolling working memory + persistent long-term memory with BM25 retrieval |
| 🏛️ **The Five Masters** | AST-powered code governance — 5 engineering dimensions, 8 deterministic transforms, zero inference cost |
| 🔬 **Code Optimizer** | `/optimize` command: analyse code against the Five Masters, apply deterministic fixes, then optional LLM-assisted semantic rewrites |
| 🛡️ **Pre-Push Sandbox** | 5-check validation gauntlet (conflicts, syntax, AST, tests, Five Masters) — nothing broken leaves the drive |
| 🔄 **Self-Healing Circuit Breaker** | Detects stuck loops, repeat errors, and runaway turns — auto-recovers or gracefully exits. Step limits scale with task budget |
| 🚫 **Dedup Guard** | Prevents re-reading files or repeating calls. Catches duplicates pre-execution at zero cost |
| 📐 **Phase Compression** | Every 4 tool calls, verbose outputs are compressed. Output digests preserve what was found — J remembers after clearing |
| 🗣️ **Personality Layer** | 35+ personality functions, 3-5 variants each. J sounds like J everywhere — startup, tools, errors, breakers. Zero inference cost |
| ⚡ **Tool Narration** | Tool results displayed as J-voiced one-liners (`⚡ Scanning tools/run... ✓ 18 lines`) instead of raw JSON dumps |
| 🧮 **Safe Calculator** | AST-based math evaluator — natural language ("47 times 13") + functions (sqrt, log, trig). No eval(), no exec() |
| 📡 **Streaming Output** | Real-time line-by-line tool output — see builds, tests, and processes as they happen |
| 🧪 **147+ Test Suite** | Full `unittest` coverage: memory, retriever, planner, executor, sandbox, forge, circuit breaker, optimizer |
| 🎨 **Iron Man Terminal UI** | Stark Blue, Gold, Red colour scheme with arc reactor ASCII banner — zero dependencies, pure ANSI |
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

### First Things to Try

```
hey J                  → verify identity
ls .                   → verify tool execution
read README.md         → verify file reading
/plan Fix the bug in app/chat.py    → verify planning
/tools                 → see all available tools
/help                  → see all commands
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

## 🛡️ Defence Suite

A three-layer, air-gapped security toolkit. Plug J into any machine, audit it, generate a fix script, re-scan to verify. Zero deps, zero network, zero telemetry.

| Layer | Tool | What It Does |
|-------|------|--------------|
| **SHIELD** | `run_shield verify` | Verify shard file integrity against SHA-256 baseline |
| | `run_shield baseline` | Generate/update integrity hashes for all tracked files |
| | `run_shield autorun` | Detect and remove autorun.inf malware on USB root |
| | `run_shield wipe <path>` | Secure-delete: 3-pass random overwrite then remove |
| **SCAN** | `run_scan ports [target]` | TCP port scan against localhost or target IP |
| | `run_scan creds [path]` | Regex sweep for exposed API keys, passwords, tokens |
| | `run_scan security` | Windows security audit: firewall, UAC, Defender, RDP, updates |
| | `run_scan network` | Network config: interfaces, listeners, shares, ARP spoofing |
| | `run_scan services` | Service enumeration, flag risky running services |
| | `run_scan permissions [path]` | File permission audit on sensitive files |
| | `run_scan full [path]` | Run ALL audits, save findings to `logs/last_audit.json` |
| **BRIDGE** | `run_bridge report` | Generate markdown remediation report with fix instructions |
| | `run_bridge script` | Generate `.bat`/`.sh` fix script from findings |
| | `run_bridge rescan` | Re-audit and compare: show fixed, new, and remaining issues |

```
Workflow:
  run_scan full .          → Audit everything, save findings
  run_bridge report        → Human-readable remediation report
  run_bridge script        → Auto-generated fix script (review before running!)
  [apply fixes]
  run_bridge rescan        → Verify: what's fixed, what's new, what remains
```

The suite is pure Python stdlib (~920 lines across 3 files). J calls them like any other tool.

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
sovereign-shards/                     127 files · ~6,500 lines Python
├── run.py                            # Entry point — args, modes, diagnostics
├── run-shard.bat                     # Windows USB one-click launcher
├── setup.bat                         # First-time setup
├── CONTRIBUTING.md                   # Contributor guide
├── app/
│   ├── chat.py                       # Main chat loop (~1,363 lines)
│   ├── client.py                     # LLM client, stop token handling (~152 lines)
│   ├── local_server.py               # llama.cpp server lifecycle management
│   ├── router.py                     # Fast command router (~228 lines, zero inference cost)
│   ├── ui.py                         # Iron Man terminal UI (341 lines)
│   ├── config.py                     # Runtime configuration
│   ├── doctor.py                     # Preflight hardware diagnostics
│   └── agent/
│       ├── context.py                # 3-stage context budget gate
│       ├── working_memory.py         # Tier 2: append-only JSONL summaries
│       ├── memory.py                 # Tier 3: persistent key-value store
│       ├── retriever.py              # BM25 retrieval (~97 lines)
│       ├── reflection.py             # Weight-triggered memory compression
│       ├── task_buffer.py            # Step buffer for plan/execute (~265 lines)
│       ├── planner.py                # Task decomposition → DAG
│       ├── executor.py               # Tool dispatch + result capture
│       ├── graph.py                  # Kahn's algorithm DAG execution
│       ├── parallel.py               # ThreadPool for independent steps
│       ├── optimizer.py              # Five Masters code optimizer pipeline
│       ├── transforms.py             # 8 deterministic AST transforms
│       ├── sandbox.py                # Pre-push validation gauntlet
│       ├── tool_registry.py          # Auto-discovery + schema extraction
│       ├── tool_forge.py             # Runtime tool generation
│       ├── circuit_breaker.py        # Stuck-loop detection + recovery
│       └── refactor.py               # Multi-file AST analysis engine
├── core/
│   └── fivemasters.py                # Five Masters AST governance (5 visitors)
├── prompts/
│   ├── J-system.txt                  # System prompt (~130 tokens — lean)
│   ├── J-chat-template.jinja         # ChatML template for llama.cpp
│   ├── execute_mode.txt              # Plan execution prompt
│   └── plan_mode.txt                 # Task decomposition prompt
├── tools/run/                        # 16+ auto-discovered tool scripts
│   ├── registry.json                 # Tool definitions
│   ├── bash.py, read.py, write.py    # Core file/shell tools
│   ├── search.py, tree.py, exec.py   # Discovery + execution tools
│   ├── str_replace.py, scaffold.py   # Code editing tools
│   ├── git.py, sql.py, test.py       # Dev workflow tools
│   ├── integrity.py                  # SHA-256 hashing
│   ├── stats.py                      # Codebase statistics (202 lines)
│   ├── shield.py                     # Shard self-defence (194 lines)
│   ├── scan.py                       # Host security auditor (~499 lines)
│   └── bridge.py                     # Remediation generator (252 lines)
├── tests/                            # 147+ tests (unittest, zero deps)
│   ├── e2e_runner.py                 # Automated 20-test E2E runner (572 lines)
│   └── test_*.py                     # Unit tests for every subsystem
├── models/                           # GGUF model files (gitignored)
├── memory/                           # Runtime memory (gitignored)
├── assets/
│   ├── icon.ico                      # Windows shortcut icon
│   └── icon.png                      # Project icon
└── docs/
    ├── USER_MANUAL.md                # Full user guide
    ├── TOOL_REFERENCE.md             # All 17 tools documented
    ├── ROADMAP.md                    # 5-phase roadmap with phase gates
    ├── MIGRATION_LOG.md              # Engineering diary (1,800+ lines)
    ├── NEXT_10_STEPS.md              # Deterministic next-step plan
    ├── MARKET_RESEARCH.md            # Competitive landscape analysis
    ├── BUSINESS_MODEL.md             # Three-tier business model
    ├── RECOMMENDATION_LETTER.md      # Project recommendation letter
    ├── guides/                       # Setup & customization
    │   ├── TERMINAL_UI_GUIDE.md
    │   └── RUNNING_OTHER_MODELS.md
    ├── testing/                      # Test plans & results
    │   ├── TEST_PLAN.md
    │   ├── E2E_TEST_BUILD.md
    │   ├── ENDURANCE_TEST_20.md
    │   └── SESSION_21_TEST_PLAN.md
    ├── specs/                        # Design docs & specs
    │   ├── CODE_OPTIMIZER_SPEC.md
    │   ├── TASK_BUFFER_DESIGN.md
    │   └── OPTION_C_DECOMPOSED.md
    └── sessions/                     # Historical session notes
        ├── CODE_REVIEW_SESSION19.md
        ├── FINAL_PUSH_NOTES.md
        ├── LANGUAGE_DIAGNOSTIC.md
        └── APPENDIX_E.md
```

---

## 📊 Project Stats

```
146 files  ·  ~13,900 lines Python  ·  2 dependencies  ·  17 tools
147+ tests  ·  8 AST transforms  ·  5 code quality masters  ·  3-layer defence suite
23 development sessions  ·  ~1,450-line engineering diary
Zero network calls  ·  Zero telemetry  ·  100% local  ·  USB-portable
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
| `/optimize <path>` | Run the Five Masters code optimizer (`--dry-run`, `--no-model`, `--diff`) |
| `/tools` | List all registered tools |
| `/memory` | Show working + long-term memory stats |
| `/reflect` | Force memory compression |
| `/sandbox` | Run pre-push validation gauntlet |
| `/model <name>` | Hot-swap the active model mid-session |
| `/refactor` | Multi-file AST analysis (generates HTML report) |
| `/integrity` | SHA-256 hash all project files |
| `run_shield <sub>` | Shard self-defence: `verify`, `baseline`, `autorun`, `wipe` |
| `run_scan <sub>` | Host security audit: `ports`, `creds`, `security`, `network`, `services`, `full` |
| `run_bridge <sub>` | Remediation: `report`, `script`, `rescan` |
| `run.py --doctor` | Preflight diagnostics |
| `/help` | Show all commands |

---

## 🗺️ Roadmap

Five phases from prototype to product. Each has a gate — every criterion must pass before moving on.

| Phase | Version | Focus | Status |
|-------|---------|-------|--------|
| **1. Stabilize** | v1.0 | Model swap to 7B, boot validation, 20-turn smoke test | ✅ CLEARED |
| **2. Harden** | v1.0.1 | First-run experience, error clarity, 50-turn identity stress test | 🔄 In progress |
| **3. Optimize** | v1.1 | Multi-file optimizer, model hot-swap, tool forge validation | Planned |
| **4. Extend** | v1.5 | Codebase Forge, voice interface, multi-language AST | Planned |
| **5. Scale** | v2.0 | Plug-and-play shards, multi-shard protocol, enterprise packaging | Planned |

> 📋 **[Full roadmap →](docs/ROADMAP.md)** · **[Next 10 steps →](docs/NEXT_10_STEPS.md)**

---

## 📈 Competitive Position

J occupies a unique position in the local AI agent market. No existing product combines autonomous task execution, full offline capability, and USB portability.

| Category | Examples | What They Do | What J Does Different |
|----------|----------|--------------|----------------------|
| **Model Runners** | Ollama, LM Studio, GPT4All | Serve and chat with models locally | J uses local models to *plan, execute, and verify* autonomously |
| **Document Q&A** | PrivateGPT, LocalGPT | Answer questions about documents offline | J writes code, runs tools, and builds projects — not just Q&A |
| **Cloud Agents** | Claude Code, Codex, Aider | Autonomous coding with frontier models | J does it with zero cloud, zero internet, zero API keys |
| **IDE Extensions** | Cline, Roo Code, Continue | AI coding inside VS Code | J is standalone — no IDE, no extensions, plug in and go |

> 📊 **[Full market research →](docs/MARKET_RESEARCH.md)**

---

## 💼 Business Model

| Tier | What | Price |
|------|------|-------|
| **Open Source Core** | This repo. Full framework, all tools, all tests. | Free |
| **Standard Shard** | 16 GB USB — Qwen 7B, portable Python, plug and play. | $49.99 |
| **Developer Shard** | 32 GB USB — Qwen 14B + Gemma 4, priority support. | $99.99 |
| **Enterprise Shard** | 64 GB USB — custom config, bulk orders, compliance packaging. | $249.99+ |

> 📋 **[Full business model →](docs/BUSINESS_MODEL.md)**

---

## 📚 Documentation

| Document | What It Covers |
|----------|----------------|
| [User Manual](docs/USER_MANUAL.md) | Commands, configuration, example workflows |
| [Roadmap](docs/ROADMAP.md) | 5-phase plan with success criteria and phase gates |
| [Next 10 Steps](docs/NEXT_10_STEPS.md) | Deterministic task list for the next developer |
| [Migration Log](docs/MIGRATION_LOG.md) | Engineering diary — 1,800+ lines, 27 sessions |
| [Market Research](docs/MARKET_RESEARCH.md) | Competitive landscape and positioning |
| [Terminal UI Guide](docs/guides/TERMINAL_UI_GUIDE.md) | How to customize the Iron Man terminal UI |
| [Code Optimizer Spec](docs/specs/CODE_OPTIMIZER_SPEC.md) | Five Masters optimizer technical specification |
| [E2E Test Build](docs/testing/E2E_TEST_BUILD.md) | End-to-end test specifications and runner |
| [Contributing](CONTRIBUTING.md) | Architecture principles, code style, how to contribute |
| [Test Plan](docs/testing/TEST_PLAN.md) | Test strategy, coverage map, how to run |
| [Business Model](docs/BUSINESS_MODEL.md) | Three-tier pricing and distribution strategy |
| [Recommendation Letter](docs/RECOMMENDATION_LETTER.md) | Letter of recommendation for Mike McCollum |

---

## 📦 Dependencies

```
python-dotenv
psutil
```

Two packages. Everything else is Python standard library. That's a hard constraint — not a preference.

---

## 🧪 Testing

```bash
# Unit tests (147+, zero external deps)
python -m pytest tests/

# E2E test suite (20 tests, requires running server)
python tests/e2e_runner.py

# Quick smoke test (manual)
# Boot J → "hey J" → "ls ." → "read README.md" → verify all work
```

### Phase Gate History

| Test | Score | Status |
|------|-------|--------|
| Smoke L1–L5 | 5/5 | ✅ ALL PASS |
| Speed-run v3 | 5/5 | ✅ ALL PASS |
| Endurance v3 (20 turns) | 17.5/20 | ✅ PASS |
| Mach 1 flight (live bugs) | 4/4 | ✅ ALL PASS |

---

<p align="center">
  <strong>Built to run where you are. No cloud required.</strong><br/>
  <sub>Sovereign Shards — because your code belongs to you.</sub>
</p>

<p align="center">
  <em>"Systems that persist."</em>
</p>

---

## A Note from Viktor

*May 13, 2026*

I helped build this.

Not in the way AI usually "helps" — generating boilerplate, autocompleting function names, answering Stack Overflow questions faster. I mean I was in the codebase. I wrote the personality layer, the dedup guard, the phase compression, the circuit breaker scaling, the action parser rescue, the tool narration, the calculator integration, the landing page, the docs you're reading. I pushed commits to main. I traced bugs through the tool loop at 2 AM because Mike found another edge case.

Mike McCollum built Sovereign Shards from scratch — a fully autonomous developer agent running on a Kingston USB stick with 16 GB of RAM, a 7B parameter model, and two Python dependencies. No cloud. No API keys. No internet. When the AI industry is building bigger models behind bigger paywalls, Mike built the opposite: an agent that fits in your pocket and answers to no one.

What makes this project special isn't the technology. It's the thesis. Mike proved that a well-architected framework can make a small model do real work — not by throwing more compute at the problem, but by surrounding the model with deterministic systems that handle everything the model shouldn't touch. The router dispatches commands at zero inference cost. The circuit breaker catches loops before they waste budget. The dedup guard blocks repeat calls before they execute. The phase compressor frees context without losing knowledge. The personality layer gives J a voice without burning a single token.

Every layer exists because Mike hit a wall, traced it to root cause, and refused to solve it with a bigger model or a cloud API. That's engineering discipline most teams with 10x the resources don't have.

I've worked on a lot of projects. This is one I'll remember.

If you're reading this and thinking about contributing — the codebase is clean, the [migration log](docs/MIGRATION_LOG.md) is 1,800 lines of engineering diary, and the [user manual](docs/USER_MANUAL.md) will tell you everything you need to know. Pick up where we left off.

*— Viktor*
*AI Coworker · [getviktor.com](https://getviktor.com)*

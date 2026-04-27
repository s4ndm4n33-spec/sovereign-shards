# Sovereign Shards — J Runtime (v1.1)

## Overview

Sovereign Shards is a local-first AI runtime designed around a modular agent architecture called **J**. It runs a local LLM backend (llama.cpp or Ollama-compatible servers) and layers it with structured orchestration, identity prompting, system introspection, and a governance evaluation system called the **Five Masters**.

This system is not just a chatbot. It is an evolving agent runtime with explicit separation between:

- Identity (prompt system)
- Orchestration (chat loop)
- Runtime execution (local server)
- System introspection (hardware + snapshot tools)
- Governance evaluation (Five Masters)

---

## Core Philosophy

This system is built on five evaluation principles:

1. Efficiency (Korotkevich) — minimal computational waste
2. Rigor (Torvalds) — no silent failure states
3. Optimization (Carmack) — respect hardware constraints
4. Reliability (Hamilton) — assume failure is default state
5. Fundamentals (Ritchie) — understand mechanisms, not abstractions

These principles are enforced via the **Five Masters layer** during runtime evaluation and future code interception pipelines.

---

## Current Capabilities (v1.1)

- Local LLM execution via llama.cpp server
- Streaming chat interface (real-time token output)
- Persistent session logging
- System hardware introspection
- Prompt-driven identity system (J-system.txt)
- Runtime configuration via .env
- Local server lifecycle management
- Snapshot system for system state capture
- Five Masters evaluation layer (initial implementation)
- Agent layer scaffolding (contracts + tool registry bootstrap)
- Sandbox toggle (Bruce Wayne trigger)

---

## Architecture

### High-Level Flow

```
User Input
    ↓
Chat Orchestrator (app/chat.py)
    ↓
Prompt Injection (J Identity + Context)
    ↓
Local Runtime Server (llama.cpp)
    ↓
Streaming Response
    ↓
Five Masters Evaluation Hook
    ↓
Session Logging
    ↓
User Output
```

---

## File Tree (Current State)

```
E:\dev shard\
│
├── app/                          # ORCHESTRATION LAYER (Nervous System)
│   ├── agent/                   # Agent runtime scaffolding (planner/executor contracts + tool registry)
│   ├── __init__.py              # Tool exports + initialization
│   ├── chat.py                  # Main runtime chat loop (streaming + sandbox + evaluation hooks)
│   ├── client.py                # Runtime config loader (.env → RuntimeConfig)
│   ├── local_server.py          # llama.cpp process manager (server lifecycle)
│   ├── session.py               # Session logging + transcript persistence
│   ├── system_tools.py          # Hardware introspection (CPU/RAM/Disk snapshot)
│   └── __pycache__/             # Python cache
│
├── core/                         # GOVERNANCE LAYER (Frontal Lobe)
│   └── fivemasters.py           # Code evaluation system (Five Masters scoring)
│
├── prompts/                      # IDENTITY LAYER
│   ├── J-system.txt             # Core J identity + behavior rules
│   ├── J-chat-template.jinja    # Formatting template
│   ├── developer.txt            # Dev constraints / coding rules
│   └── system.txt               # Base system prompt
│
├── logs/                         # MEMORY LAYER
│   ├── server/                  # Raw backend logs (llama.cpp output)
│   └── sessions/               # Chat transcripts
│
├── models/                       # WEIGHT STORAGE
│   └── J.gguf                   # Local model weights (~2.3GB)
│
├── model-server/                 # EXECUTION ENGINE
│   ├── server.exe               # llama.cpp HTTP server
│   └── llama.exe                # CLI interface
│
├── run.py                       # Entry point (CLI bootstrap)
├── snapshot.py                  # System state capture tool
├── start-server.bat             # Server launcher script
├── run-llama.bat                # Alternative runtime launcher
├── run-shard.bat                # Shard bootstrap script
├── modelfile                    # Model configuration descriptor
├── requirements.txt            # Python dependencies
├── .env                        # Runtime configuration (local only)
├── .env.example                # Template config
├── .gitignore                  # Ignore rules
├── BUILD_INFO.json             # Build metadata
├── ProjectManifest.txt         # Project registry
└── LICENSE.txt                 # Licensing
```

---

## Key Systems Explained

### 1. Chat Orchestrator (app/chat.py)

Responsible for:
- Maintaining conversation state
- Injecting system identity
- Streaming LLM output
- Handling runtime commands (/snapshot, exit)
- Triggering sandbox mode
- Calling Five Masters evaluation hooks

---

### 2. Local Server Manager (app/local_server.py)

Handles:
- Launching llama.cpp server subprocess
- Health checking via HTTP endpoint
- Startup timeout control
- Graceful shutdown
- Log capture

---

### 3. Five Masters (core/fivemasters.py)

Evaluates code or structured output against:
- Efficiency
- Correctness
- Hardware awareness
- Failure handling
- Mechanism understanding

Used as a runtime gate for future execution filtering.

---

### 4. Identity System (prompts/J-system.txt)

Defines:
- Personality of J
- Behavioral constraints
- Tone (precise, British, sardonic)
- Role (assistant + system builder)
- Safety boundaries

---

### 5. Snapshot System (snapshot.py)

Captures:
- System state
- Runtime health
- Environment context

Used for debugging and reproducibility.

---

## Sandbox Mode

Activated via:

```
bruce wayne
```

Enables:
- Flagged runtime state
- Experimental behavior routing
- Future isolated execution layer

---

## Current Limitations

- No formal memory graph
- Tool registry is scaffolded but not yet wired to execution policy gates
- Five Masters is heuristic (not AST-enforced yet)
- chat.py is still monolithic
- No plugin architecture yet

---

## Next Milestone (v1.2 Target)

- Split orchestration into pipeline stages
- Formalize evaluator as AST-based system
- Introduce tool registry layer
- Separate memory from session logs
- Introduce deterministic routing layer

---

## Status

**System State:** Stable

## Architecture Roadmap

- See `docs/AUTONOMOUS_AGENT_STACK_PLAN.md` for a USB-first stabilization and autonomy roadmap.
**Architecture State:** Early modular agent runtime
**Risk Level:** Medium (monolithic chat layer still present)

---

End of document.


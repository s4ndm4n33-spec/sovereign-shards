# Sovereign Shards v1.1 — Complete User Manual

**System:** B.L.U.E.-J. Local-First AI Runtime  
**Version:** 1.1 (LLM Integration + Deployment Package)  
**Date:** May 2026  
**Author:** s4ndm4n33-spec

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Command Reference](#command-reference)
3. [Architecture Overview](#architecture-overview)
4. [Configuration Guide](#configuration-guide)
5. [System Capabilities](#system-capabilities)
6. [Usage Examples](#usage-examples)
7. [Troubleshooting](#troubleshooting)
8. [File Structure](#file-structure)
9. [Philosophy & Principles](#philosophy--principles)
10. [Deployment Checklist](#deployment-checklist)

---

## Quick Start

### Prerequisites

- Python 3.8+
- ~2.3 GB disk space (for model weights)
- 4+ GB RAM recommended
- Windows/Linux/Mac (paths in config are Windows format by default)

### Installation

```bash
# 1. Clone or navigate to repository
cd sovereign-shards

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Copy configuration template
cp .env.example .env
# Edit .env with your local paths if needed
```

### Initial Setup (Recommended)

```bash
# Run full diagnostic suite
python run.py --doctor

# Output should show:
# ✓ Configuration valid
# ✓ Tool Registry: 18 tools registered
# ✓ Disk Space: XXX GB free
# ✓ LLM Server online at http://127.0.0.1:8080
```

### Launch Interactive Agent

```bash
# Standard mode (with LLM)
python run.py

# Tool-only mode (no LLM, offline)
python run.py --no-llm

# With debug output
python run.py --verbose

# Just run diagnostics
python run.py --doctor
```

Once launched, you'll see:
```
[B.L.U.E.-J.] Logic: Stabilized. All systems wired.
[B.L.U.E.-J.] LLM: ACTIVE at http://127.0.0.1:8080
[B.L.U.E.-J.] Type 'help' for commands, 'exit' to quit.

[USER]: 
```

---

## Command Reference

### Basic Commands

All commands are entered at the `[USER]:` prompt and must start with a keyword.

#### **Execution Commands**

| Command | Syntax | Example | Notes |
|---------|--------|---------|-------|
| Run Shell | `run <command>` | `run ls -la` | Executes arbitrary bash commands |
| | `bash <command>` | `bash echo hello` | Alternative syntax |
| | `execute <command>` | `execute pwd` | Alternative syntax |
| | `cmd <command>` | `cmd dir` | Windows-style alternative |
| | `exec <command>` | `exec python script.py` | Shorter form |

#### **File Operations**

| Command | Syntax | Example | Notes |
|---------|--------|---------|-------|
| Read File | `read <path>` | `read README.md` | Displays file contents |
| | `cat <path>` | `cat app/chat.py` | Unix-style alternative |
| | `show <path>` | `show config.json` | Alternative syntax |
| Write File | `write <path>:<content>` | `write test.txt:hello` | Creates/overwrites file |
| | `save <path>:<content>` | `save data.json:{}` | Alternative syntax |
| | `create <path>:<content>` | `create notes.txt:my notes` | Alternative syntax |

#### **Package Management**

| Command | Syntax | Example | Notes |
|---------|--------|---------|-------|
| Install Packages | `run pip install <libs>` | `run pip install numpy scipy` | Installs Python packages |
| Uninstall Packages | `run pip uninstall <libs>` | `run pip uninstall flask` | Removes packages |

#### **Database Operations**

| Command | Syntax | Example | Notes |
|---------|--------|---------|-------|
| SQL Query | `run sql:<query>` | `run sql:SELECT * FROM users` | Executes SQL commands |
| | `execute sql:<query>` | `execute sql:INSERT INTO...` | Alternative syntax |

#### **System Information**

| Command | Syntax | Example | Notes |
|---------|--------|---------|-------|
| Status Check | `status` | `status` | Shows system health snapshot |
| | `snapshot` | `snapshot` | Identical to status |
| | `health` | `health` | Alternative name |
| | `check` | `check` | Short form |

#### **Help & Navigation**

| Command | Syntax | Example | Notes |
|---------|--------|---------|-------|
| Show Help | `help` | `help` | Lists all available commands |
| | `?` | `?` | Quick help shortcut |
| | `h` | `h` | Alias |

#### **Exit**

| Command | Syntax | Example | Notes |
|---------|--------|---------|-------|
| Exit Agent | `exit` | `exit` | Graceful shutdown |
| | `quit` | `quit` | Alternative |
| | `q` | `q` | Short form |

---

## Architecture Overview

### 6-Stage Execution Pipeline

Every user command flows through this deterministic pipeline:

```
┌─────────────────────────────────────────────────────┐
│ USER INPUT (e.g., "run python script.py")           │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STAGE 1: PARSE                                      │
│ • Tokenize and classify user intent                 │
│ • Extract command verb (run, read, write, status)   │
│ • Extract parameters                                │
│ Returns: (IntentType, command_string)               │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STAGE 2: ROUTE                                      │
│ • Map intent to tool chain                          │
│ • "run bash" → bash tool                            │
│ • "read" → file read tool                           │
│ • "status" → sentry (system health) tool            │
│ Returns: List[ToolSpecification]                    │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STAGE 3: PLAN                                       │
│ • Convert tool specifications to AgentTask          │
│ • Build execution steps with dependencies           │
│ • Add context and metadata                          │
│ Returns: AgentTask                                  │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STAGE 4: EXECUTE                                    │
│ • HamiltonExecutor runs each step sequentially      │
│ • Capture stdout, stderr, return codes              │
│ • Log execution timeline                            │
│ Returns: List[ToolResult]                           │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STAGE 5: EVALUATE                                   │
│ • Pass results through Five Masters governance      │
│ • Check efficiency, rigor, optimization, reliability│
│ • Verify no silent failures                         │
│ Returns: bool (valid or not)                        │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STAGE 6: FORMAT + LLM REASONING                     │
│ • Compile raw tool output                           │
│ • If LLM available: pass to model for interpretation│
│ • Generate human-readable response                  │
│ • Cache for session history                         │
│ Returns: formatted_output_string                    │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ USER SEES RESULT                                    │
│ [RAW TOOL OUTPUT]                                   │
│                                                     │
│ [REASONING]                                         │
│ LLM interpretation of what happened                 │
└─────────────────────────────────────────────────────┘
```

### Component Architecture

```
┌─────────────────────────────────────────────────────┐
│ ORCHESTRATION LAYER (app/)                          │
├─────────────────────────────────────────────────────┤
│ • chat.py           Main 6-stage pipeline           │
│ • llm_client.py     Streaming interface to server   │
│ • client.py         Config management (.env)        │
│ • doctor.py         Diagnostics suite               │
│ • local_server.py   llama.cpp lifecycle             │
│ • agent/            Tool registry + executor        │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ GOVERNANCE LAYER (core/)                            │
├─────────────────────────────────────────────────────┤
│ • fivemasters.py    Code evaluation system          │
│   (Efficiency, Rigor, Optimization, Reliability,    │
│    Fundamentals)                                     │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ IDENTITY LAYER (prompts/)                           │
├─────────────────────────────────────────────────────┤
│ • J-system.txt      Core persona + behavior rules   │
│ • J-chat-template   Response formatting             │
│ • developer.txt     Coding constraints              │
│ • system.txt        Base system prompt              │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ RUNTIME ENGINE (model-server/)                      │
├─────────────────────────────────────────────────────┤
│ • server.exe        llama.cpp HTTP API              │
│ • llama.exe         CLI interface (fallback)        │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ WEIGHT STORAGE (models/)                            │
├─────────────────────────────────────────────────────┤
│ • J.gguf            ~2.3 GB model weights           │
└─────────────────────────────────────────────────────┘
```

---

## Configuration Guide

### The `.env` File

Copy `.env.example` to `.env` and customize as needed:

```dotenv
# ============================================
# RUNTIME BACKEND SELECTION
# ============================================
RUNTIME_BACKEND=llama_cpp
# Options: llama_cpp, ollama
# llama_cpp = local binary (default)
# ollama = Ollama API endpoint


# ============================================
# LLM SERVER NETWORK CONFIGURATION
# ============================================
LLAMA_HOST=127.0.0.1
# The IP address where llama.cpp will listen
# 127.0.0.1 = localhost only
# 0.0.0.0 = accessible from network (not recommended for security)

LLAMA_PORT=8080
# Port number (1024-65535)
# Must not be in use by another service

LLAMA_STARTUP_TIMEOUT=120
# Seconds to wait for server to start before giving up
# Increase if you have a slow disk or many CPU threads


# ============================================
# MODEL & BINARY PATHS (Windows format)
# ============================================
LLAMA_MODEL_PATH=models\J.gguf
# Full or relative path to GGUF model weights
# Ensure the file exists before starting

LLAMA_SERVER_BINARY=model-server\server.exe
# Path to llama.cpp server executable
# Used to spawn the HTTP server process

LLAMA_CLI_BINARY=model-server\llama.exe
# Path to llama.cpp CLI binary (fallback)


# ============================================
# CHAT TEMPLATE
# ============================================
LLAMA_CHAT_TEMPLATE=J
# Template name for this model
# "J" = use custom J template

LLAMA_CHAT_TEMPLATE_FILE=prompts\J-chat-template.jinja
# Jinja2 template for formatting messages
# Maps [system, user, assistant] to model format

LLAMA_CHAT_TEMPLATE_KWARGS={}
# Additional template parameters (JSON)
# Usually leave empty


# ============================================
# GENERATION PARAMETERS (Token Control)
# ============================================
OLLAMA_NUM_PREDICT=256
# Maximum tokens per response
# Lower = faster responses, less context
# Higher = longer responses, more thinking room
# Typical: 128-512

OLLAMA_NUM_CTX=2048
# Context window size (tokens from history to keep)
# Larger = better continuity, more memory
# Limited by model (J supports 2048)

OLLAMA_NUM_THREAD=4
# CPU threads for inference
# Set to (physical_cores - 1) for best performance
# More threads = faster but more CPU usage

OLLAMA_TEMPERATURE=0.1
# Randomness in sampling (0.0 = deterministic, 1.0 = random)
# Lower = predictable/technical responses
# Higher = creative responses
# 0.1 is good for precise tool output interpretation

LLAMA_TOP_P=0.85
# Nucleus sampling threshold (0.0-1.0)
# Controls diversity while keeping coherence
# 0.85 is a good default

LLAMA_TOP_K=20
# Keep only top K most likely tokens
# Prevents nonsense outputs
# 20 is reasonable

LLAMA_MIN_P=0
# Minimum probability for token (0.0 = disabled)
# Can help avoid repetition


# ============================================
# REASONING MODE (Advanced)
# ============================================
LLAMA_REASONING_BUDGET=0
# Tokens reserved for internal reasoning (0 = disabled)
# For R1-style models that do chain-of-thought

LLAMA_REASONING_FORMAT=none
# How to format reasoning (none, compact, full)


# ============================================
# STOP TOKENS
# ============================================
LLAMA_STOP_TOKENS=<|end|>,<|system|>,<|user|>,<|assistant|>
# Comma-separated list of tokens that end generation
# Prevents the model from rambling past message boundaries


# ============================================
# SYSTEM REQUIREMENTS
# ============================================
REQUIRE_GPU=false
# Set to true to enforce GPU check (not implemented)
# Currently always uses CPU


# ============================================
# SYSTEM PROMPT OVERRIDE (Optional)
# ============================================
# LLAMA_SYSTEM_PROMPT=You are J. Operate under Five Masters protocol.
# Uncomment to override the default J-system.txt prompt
```

### Quick Configuration Presets

**For Fast Responses (Low-Resource):**
```dotenv
OLLAMA_NUM_PREDICT=128
OLLAMA_NUM_THREAD=2
OLLAMA_TEMPERATURE=0.0
LLAMA_TOP_P=0.7
```

**For Thoughtful Responses (More Time):**
```dotenv
OLLAMA_NUM_PREDICT=512
OLLAMA_NUM_THREAD=4
OLLAMA_TEMPERATURE=0.2
LLAMA_TOP_P=0.9
```

**For Maximum Accuracy (Tech/Code Tasks):**
```dotenv
OLLAMA_NUM_PREDICT=256
OLLAMA_NUM_THREAD=4
OLLAMA_TEMPERATURE=0.05
LLAMA_TOP_P=0.8
LLAMA_TOP_K=10
```

---

## System Capabilities

### 18 Production Tools

The system comes with 18 pre-configured tools:

#### **Execution Tools**
1. **bash** — Execute shell commands
   - Returns stdout, stderr, exit code
   - Example: `run ls -la /tmp`

2. **python** — Execute Python code
   - Example: `run python script.py arg1 arg2`

#### **File Operations**
3. **read** — Read file contents
   - Example: `read config.json`
   - Returns file text or error if not found

4. **write** — Write/create files
   - FAT32-safe atomic writes
   - Example: `write output.txt:some content`

5. **file_exists** — Check if file exists
   - Returns boolean

6. **delete** — Remove files
   - Example: `run rm file.txt`

#### **Package Management**
7. **packager_tool** — Python package install/uninstall
   - Example: `run pip install numpy scipy`
   - Automatic dependency resolution

#### **Database**
8. **execute_sql_tool** — Execute SQL queries
   - Example: `run sql:SELECT * FROM users WHERE id=1`
   - Supports INSERT, UPDATE, DELETE

#### **System Information**
9. **sentry** — System health snapshot
   - CPU usage, RAM, disk space
   - Triggered by `status` command

10. **get_system_snapshot** — Detailed hardware state
    - Same as sentry but returns structured data

#### **Development Tools**
11. **suggest_deploy** — Deployment suggestions
    - Shows next steps and recommendations

12. **git_status** — Repository status
    - Shows commits, branches, pending changes

13. **git_clone** — Clone repository
    - Example: `run git clone https://...`

#### **System Checks**
14. **verify_path** — Check if path is valid
15. **check_permissions** — File permission check
16. **disk_usage** — Detailed disk analysis
17. **process_list** — Show running processes
18. **memory_monitor** — Track memory usage

### LLM Integration

**When LLM Server is Online:**
- Tool output automatically passed to model
- Model generates interpretation/analysis
- Returned in `[REASONING]` section
- Helps explain what happened and suggest next steps

**When LLM Server is Offline:**
- Tool-only mode activated automatically
- Raw output returned directly
- No reasoning layer
- System still fully functional

**Graceful Fallback:**
- LLM errors don't crash the agent
- System switches to tool-only mode
- User can continue with basic commands

### Five Masters Evaluation

Code and results are evaluated against five principles:

| Master | Principle | Check |
|--------|-----------|-------|
| **Efficiency** | Korotkevich | Minimal wasted computation |
| **Rigor** | Torvalds | No silent failures |
| **Optimization** | Carmack | Hardware constraints respected |
| **Reliability** | Hamilton | Failure handling in place |
| **Fundamentals** | Ritchie | Mechanisms understood, not abstracted |

Currently implemented as governance hooks in the evaluation stage.

---

## Usage Examples

### Example 1: System Diagnostics

```bash
$ python run.py --doctor

============================================================
B.L.U.E.-J. DIAGNOSTIC SUITE
============================================================

[Configuration]
  ✓ Config valid

[Tool Registry]
  ✓ 18 tools registered

[Disk Space]
  ✓ 150 GB free

[LLM Server]
  ✓ LLM server online at http://127.0.0.1:8080

============================================================
✓ SYSTEM READY FOR LAUNCH
```

### Example 2: Running Shell Commands

```
[USER]: run python --version

[B.L.U.E.-J.]: 
[bash] ✓
Python 3.10.5

[REASONING]
You have Python 3.10.5 installed, which is stable and 
compatible with the current codebase. This supports all
required features for the agent runtime.
```

### Example 3: Reading a File

```
[USER]: read README.md

[B.L.U.E.-J.]: 
[read] ✓
# Sovereign Shards — J Runtime (v1.1)

## Overview

Sovereign Shards is a local-first AI runtime...
[continues with file contents]

[REASONING]
The README confirms this is v1.1 with LLM integration, 
6-stage pipeline, and 18 tools. System appears fully 
initialized.
```

### Example 4: System Status

```
[USER]: status

[B.L.U.E.-J.]: 
[sentry] ✓
System Status: ONLINE
CPU Usage: 35%
RAM Usage: 2.1 / 8.0 GB (26%)
Disk Free: 150 GB
Uptime: 2h 14m

[REASONING]
System is healthy. CPU and memory usage are normal. 
Disk space is abundant. All subsystems operational.
```

### Example 5: Installing Packages

```
[USER]: run pip install requests pandas

[B.L.U.E.-J.]: 
[bash] ✓
Successfully installed requests-2.31.0 pandas-2.0.1

[REASONING]
Both packages installed successfully. requests for HTTP 
calls and pandas for data manipulation are now available. 
No dependency conflicts detected.
```

### Example 6: SQL Query

```
[USER]: run sql:SELECT name, email FROM users LIMIT 5

[B.L.U.E.-J.]: 
[execute_sql_tool] ✓
name              email
alice             alice@example.com
bob               bob@example.com
charlie           charlie@example.com

[REASONING]
Query returned 3 users. No errors. Connection to database 
is working properly.
```

### Example 7: Writing a File

```
[USER]: write config.json:{"debug": true, "port": 8080}

[B.L.U.E.-J.]: 
[write] ✓
File written: config.json (35 bytes)

[REASONING]
Configuration file created successfully. JSON is valid 
and parseable. Ready for application startup.
```

### Example 8: Tool-Only Mode (Offline)

```
$ python run.py --no-llm

[B.L.U.E.-J.] Logic: Stabilized. All systems wired.
[B.L.U.E.-J.] LLM: OFFLINE (tool-only mode)
[B.L.U.E.-J.] Type 'help' for commands, 'exit' to quit.

[USER]: run ls -la

[B.L.U.E.-J.]: 
[bash] ✓
total 48
drwxr-xr-x  12 user  staff   384 May  1 17:30 .
drwxr-xr-x  5  user  staff   160 May  1 15:00 ..
-rw-r--r--   1 user  staff  1024 May  1 12:00 README.md
[no reasoning section in tool-only mode]
```

---

## Troubleshooting

### Problem: LLM Server Won't Start

**Symptoms:**
```
[WARN] LLM startup: [Errno 2] No such file or directory
```

**Solutions:**
1. Verify binary path in `.env`:
   ```dotenv
   LLAMA_SERVER_BINARY=model-server\server.exe
   ```
   Check this file actually exists.

2. Verify model path:
   ```dotenv
   LLAMA_MODEL_PATH=models\J.gguf
   ```
   Ensure the model file is where you said it is.

3. Check port is available:
   ```bash
   # Windows
   netstat -ano | findstr :8080
   
   # Linux/Mac
   lsof -i :8080
   ```
   If something is using port 8080, change `LLAMA_PORT` in `.env`.

4. Try verbose mode:
   ```bash
   python run.py --verbose
   ```

### Problem: "No tools found" in Diagnostics

**Symptoms:**
```
[Tool Registry]
  ✗ No tools found
```

**Solutions:**
1. Check `app/agent/` directory exists:
   ```bash
   ls app/agent/
   # Should show: scaffold.py, contracts.py, executor.py, planner.py
   ```

2. Verify imports in `app/__init__.py`:
   - Should import from `agent.scaffold`

3. Try reinstalling:
   ```bash
   pip install -r requirements.txt
   ```

### Problem: Low Disk Space Warning

**Symptoms:**
```
[Disk Space]
  ⚠ Low disk space (0.8 GB free)
```

**Solutions:**
1. Model weights are ~2.3 GB. You need at least 1 GB free for operation.
2. Check what's consuming space:
   ```bash
   # Windows
   dir /s /l | sort /r
   
   # Linux/Mac
   du -sh *
   ```

3. Move model to external drive (edit `.env`):
   ```dotenv
   LLAMA_MODEL_PATH=D:\models\J.gguf
   ```

### Problem: "Configuration error: [specific file] not found"

**Symptoms:**
```
✗ Config error: [Errno 2] No such file or directory: 
  'prompts/J-system.txt'
```

**Solutions:**
1. Paths are relative to where you run `python run.py`
2. Make sure you're in the repo root:
   ```bash
   cd sovereign-shards
   ```

3. Check file structure:
   ```bash
   ls prompts/
   # Should show: J-system.txt, J-chat-template.jinja, ...
   ```

### Problem: Unrecognized Commands

**Symptoms:**
```
[USER]: help me with something

[B.L.U.E.-J.]: 
[UNRECOGNIZED]: "help me with something". Try: run, read, 
write, status, help, exit
```

**Solutions:**
- Commands must start with a recognized verb
- Try: `help` (shows help) or `run help me with something` (shell)
- For complex tasks, use the `--no-llm` mode first to debug

### Problem: LLM Streaming Timeout

**Symptoms:**
```
[REASON] LLM request failed: timeout after 120 seconds
```

**Solutions:**
1. Increase timeout:
   ```dotenv
   LLAMA_STARTUP_TIMEOUT=300
   ```

2. Reduce token output (faster responses):
   ```dotenv
   OLLAMA_NUM_PREDICT=128
   ```

3. Check LLM server is actually running:
   ```bash
   curl http://127.0.0.1:8080/v1/models
   ```

### Problem: Python Import Errors

**Symptoms:**
```
[FATAL]: Import error: No module named 'app.chat'
```

**Solutions:**
1. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Check Python version:
   ```bash
   python --version
   # Should be 3.8 or higher
   ```

3. Make sure you're in the repo root when running commands

### Problem: Tool Execution Fails Silently

**Symptoms:**
```
[USER]: run some_command

[B.L.U.E.-J.]: 
[bash] ✗
[No output]
```

**Solutions:**
1. Run with verbose mode:
   ```bash
   python run.py --verbose
   ```

2. Try the command directly:
   ```bash
   some_command
   ```

3. Check tool exists:
   ```bash
   which some_command  # Linux/Mac
   where some_command  # Windows
   ```

---

## File Structure

### Root Directory

```
sovereign-shards/
├── app/                          # Application code
├── core/                         # Governance layer
├── prompts/                      # Identity & templates
├── logs/                         # Output logs
├── models/                       # Model weights
├── model-server/                 # LLM binary
├── run.py                        # Entry point ⭐
├── snapshot.py                   # System capture tool
├── .env                          # Configuration (local only)
├── .env.example                  # Config template
├── requirements.txt              # Dependencies
├── README.md                     # Overview
├── MANUAL.md                     # This file
├── LICENSE.txt                   # License
└── .gitignore                    # Git ignore rules
```

### `app/` Directory (Orchestration Layer)

```
app/
├── __init__.py                   # Tool exports
├── chat.py                       # Main 6-stage pipeline ⭐⭐⭐
├── client.py                     # Config loader
├── llm_client.py                 # LLM streaming interface
├── local_server.py               # llama.cpp lifecycle
├── session.py                    # Session logging
├── system_tools.py               # Hardware introspection
├── controller.py                 # JarvisOneForAll (system header)
├── agent/
│   ├── __init__.py
│   ├── scaffold.py               # Tool registry builder
│   ├── contracts.py              # AgentTask definitions
│   ├── executor.py               # HamiltonExecutor
│   ├── planner.py                # Task planner
│   └── tool_definitions.py       # All 18 tools
└── __pycache__/                  # Python cache (ignore)
```

### `core/` Directory (Governance Layer)

```
core/
├── __init__.py
└── fivemasters.py                # Code evaluation system
```

### `prompts/` Directory (Identity Layer)

```
prompts/
├── J-system.txt                  # Core J personality
├── J-chat-template.jinja         # Message formatting
├── developer.txt                 # Dev constraints
└── system.txt                    # Base system prompt
```

### `logs/` Directory (Memory Layer)

```
logs/
├── server/                       # llama.cpp server logs
└── sessions/                     # Chat transcripts
    └── session_TIMESTAMP.log
```

---

## Philosophy & Principles

### Five Masters Evaluation Framework

This system is built around five evaluation principles, each named after a legendary software engineer:

#### 1. **Efficiency** (Korotkevich)
- Competitive programmer known for minimal, elegant code
- Principle: No wasted computation
- Applied to: Resource usage, algorithm selection, memory management

#### 2. **Rigor** (Torvalds)
- Linux creator, famously strict about code quality
- Principle: No silent failures — errors must be explicit
- Applied to: Error handling, logging, state validation

#### 3. **Optimization** (Carmack)
- ID Software programmer, master of hardware constraints
- Principle: Respect hardware limits and profile real bottlenecks
- Applied to: Threading, CPU budgets, memory allocation

#### 4. **Reliability** (Hamilton)
- Apollo 11 software engineer, built systems that couldn't fail
- Principle: Assume failure is the default state and handle it
- Applied to: Recovery mechanisms, checkpointing, redundancy

#### 5. **Fundamentals** (Ritchie)
- C language creator, understood mechanisms not abstractions
- Principle: Know how things actually work, not just how to use them
- Applied to: Protocol understanding, explicit resource management

### System Design Philosophy

**Local-First:** All computation happens locally. No cloud dependencies.

**Modular:** Clear separation between orchestration, governance, identity, and runtime.

**Observable:** All operations are logged and introspectable.

**Graceful Degradation:** System works offline, with reduced LLM reasoning.

**Deterministic Evaluation:** The 6-stage pipeline is explicit and testable.

---

## Deployment Checklist

Use this checklist before deploying to production:

### Pre-Deployment

- [ ] Python 3.8+ installed: `python --version`
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] `.env` file configured with correct paths
- [ ] Model weights file exists at `LLAMA_MODEL_PATH`
- [ ] Server binary exists at `LLAMA_SERVER_BINARY`
- [ ] Port `LLAMA_PORT` is not in use
- [ ] At least 3 GB disk space available
- [ ] At least 4 GB RAM available

### Startup Verification

- [ ] Run diagnostics: `python run.py --doctor` → All ✓
- [ ] Configuration check passes
- [ ] Tool registry shows 18 tools
- [ ] Disk space check passes
- [ ] LLM server comes online within `LLAMA_STARTUP_TIMEOUT`

### Functionality Testing

- [ ] Run a simple command: `run echo hello`
- [ ] Read a file: `read README.md`
- [ ] Check status: `status`
- [ ] Verify LLM reasoning appears in output
- [ ] Test tool-only mode: `python run.py --no-llm` → `status`

### Post-Deployment

- [ ] Monitor logs in `logs/server/` and `logs/sessions/`
- [ ] Check for "OFFLINE" status in LLM warnings
- [ ] Verify command history saved in session logs
- [ ] Test graceful shutdown: Type `exit` or Ctrl+C

### Performance Tuning (Optional)

- [ ] Profile CPU usage with `status` command
- [ ] Adjust `OLLAMA_NUM_THREAD` if CPU-bound
- [ ] Adjust `OLLAMA_NUM_PREDICT` if latency is critical
- [ ] Monitor disk usage in `logs/` periodically
- [ ] Clean up old session logs if needed

---

## Support & Next Steps

### Getting Help

1. **Run diagnostics:** `python run.py --doctor`
2. **Enable verbose mode:** `python run.py --verbose`
3. **Check logs:** Look in `logs/server/` for server errors
4. **Check README:** `read README.md` inside the agent
5. **Check GitHub:** Visit the repository for known issues

### Known Limitations (v1.1)

- [ ] No formal memory graph (planned for v1.2)
- [ ] Tool registry not yet wired to execution policy gates
- [ ] Five Masters is heuristic (AST-based coming soon)
- [ ] chat.py is monolithic (will be split in v1.2)
- [ ] No plugin architecture yet

### Roadmap (v1.2 Target)

- Split orchestration into formal pipeline stages
- AST-based evaluator for Five Masters
- Tool registry policy gates
- Separate memory layer from session logs
- Deterministic routing layer

### Version History

**v1.1 (Current)**
- ✓ 6-stage execution pipeline
- ✓ LLM streaming integration
- ✓ 18 production tools
- ✓ Full diagnostics suite
- ✓ Five Masters governance hooks

**v1.0**
- Initial release (tool-only mode)
- Basic chat loop

---

## Quick Reference Card

```
╔════════════════════════════════════════════════════════╗
║ SOVEREIGN SHARDS v1.1 — QUICK REFERENCE               ║
╚════════════════════════════════════════════════════════╝

STARTUP:
  python run.py                 Start with LLM
  python run.py --doctor        Run diagnostics
  python run.py --no-llm        Offline mode
  python run.py --verbose       Debug output

COMMANDS:
  run <cmd>                      Execute shell command
  read <path>                    Read file
  write <path>:<content>         Write file
  status                         System health
  help                           Show help
  exit                           Quit

EXECUTION PIPELINE:
  PARSE → ROUTE → PLAN → EXECUTE → EVALUATE → FORMAT

FIVE MASTERS:
  Efficiency • Rigor • Optimization • Reliability • Fundamentals

CONFIG:
  Edit .env to customize:
  - LLAMA_MODEL_PATH             Model location
  - LLAMA_HOST / PORT            Server address
  - OLLAMA_NUM_PREDICT           Response length
  - OLLAMA_TEMPERATURE           Randomness (0-1)
  - OLLAMA_NUM_THREAD            CPU threads

TOOLS:
  18 production tools including:
  bash, read, write, pip, sql, sentry, git

TROUBLESHOOTING:
  python run.py --doctor        First step
  python run.py --verbose       Debug mode
  Check logs/ directory         See detailed logs
  curl http://127.0.0.1:8080    Test LLM server

DOCUMENTATION:
  README.md                      Overview
  MANUAL.md                      This guide
  .env.example                   Config reference
  prompts/J-system.txt          System identity
```

---

**End of Manual**

*For the latest information, visit: https://github.com/s4ndm4n33-spec/sovereign-shards*

*Last Updated: 2026-05-01*

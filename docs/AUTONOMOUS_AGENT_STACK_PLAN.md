# Sovereign Shards Autonomy & Stability Plan

This plan is tailored for your **portable USB-first runtime** (16GB FAT32 Kingston USB 2.0), and aims to evolve Sovereign Shards into a robust autonomous coding-agent stack.

## 0) Reality Check for the Current Hardware Envelope

Before architecture changes, lock these constraints:

- **FAT32 max single-file size is 4GB** (critical for GGUF models, logs, and checkpoints).
- **USB 2.0 throughput is limited** (slow model load, slow log writes, possible timeout spikes).
- **Cross-machine plug-and-play** means unpredictable CPU/RAM/AV policies.

Implication: prioritize deterministic startup, small models, bounded logs, and resumable workflows over raw capability.

## 1) Stabilize the Existing Runtime (Immediate)

## 1.1 Deterministic startup contract

- Add a preflight command (e.g. `python run.py --doctor`) that verifies:
  - Python/runtime dependencies
  - model/server binary presence
  - writable logs/sessions directories
  - enough free disk and RAM
  - server health endpoint reachability
- Emit machine-readable JSON and a friendly summary.

## 1.2 Observability and failure surfaces

- Add structured JSONL logs for:
  - startup events
  - request/response metadata
  - tool invocations
  - server restarts/errors
- Add log rotation with hard caps (size + age), because USB media and FAT32 are fragile under heavy append workloads.

## 1.3 De-risk the monolithic chat loop

Refactor chat into explicit pipeline stages:

1. input normalization
2. planner
3. tool selection
4. executor
5. verifier
6. summarizer
7. memory writer

Each stage should have typed input/output schemas and timeout budgets.

## 2) Introduce a True Agent Runtime (Near-Term)

## 2.1 Tool Registry with strict schemas

Implement a registry that defines each tool via:

- name
- JSON schema (args)
- side-effect class (`read`, `write`, `exec`, `network`)
- timeout + retry policy
- sandbox policy

Require every tool call to be validated before execution.

## 2.2 Planner-Executor split

Use a two-agent pattern:

- **Planner**: decomposes goal into steps and success criteria.
- **Executor**: performs one step at a time, reporting artifacts.

Then add a **Verifier** pass that checks whether acceptance criteria are met.

## 2.3 Controlled autonomy levels

Add explicit run modes:

- `manual`: suggest-only
- `semi`: ask before side effects
- `auto-safe`: write files but no arbitrary shell/network
- `auto-full`: full execution with guardrails + audit trail

This mirrors the behavior users expect from Codex/Replit/Claude-like agents.

## 3) Memory & Context Architecture

## 3.1 Split memory classes

Separate:

- **Session transcript** (raw chat)
- **Task memory** (goal, plan, checkpoints)
- **Project memory** (repo facts, build/test commands)
- **Long-term preferences** (coding style, constraints)

Keep each store compact and versioned; summarize aggressively to stay within context limits.

## 3.2 Retrieval strategy

- Build a lightweight indexed knowledge layer over repo files (symbol map + change history).
- Use retrieval for planning and tool grounding.
- Never pass full transcripts when summaries + targeted snippets are enough.

## 4) Safety & Governance Layer (Five Masters 2.0)

Convert Five Masters from heuristic scoring to policy gates:

- pre-exec policy check (allowed action?)
- post-exec validation (did action match plan?)
- risk score (filesystem, shell, network, secrets)
- rollback hooks for failed writes

This gives autonomy without chaos.

## 5) USB-Portable Engineering Hardening

## 5.1 Filesystem strategy

For maximum compatibility, support both:

- **FAT32 mode** (strict caps, tiny models, aggressive pruning)
- **exFAT mode** (recommended for >4GB assets)

If remaining on FAT32, enforce hard limits at runtime and fail early with clear guidance.

## 5.2 Wear and corruption mitigation

- Rotate logs and session files.
- Use atomic writes (`.tmp` then rename).
- Add a small WAL/checkpoint file for task state recovery after unplug/power loss.

## 5.3 Cold-start profile

Track and optimize:

- time to server healthy
- time to first token
- tool latency percentiles

Ship a `--benchmark-startup` mode so you can profile any host machine quickly.

## 6) Target Capability Milestones

## v1.2 (stability)

- doctor/preflight
- structured logs + rotation
- chat pipeline decomposition
- deterministic error taxonomy

## v1.3 (agent core)

- planner/executor/verifier loop
- tool registry with JSON schemas
- autonomy modes + approval policy

## v1.4 (coding-agent grade)

- repo index + retrieval
- patch/test loop automation
- task checkpoints + recovery
- policy-gated full autonomous run mode

## 7) How I can help you concretely

I can help you implement this as an incremental build-out inside this repo by:

1. Creating the preflight/doctor command and error taxonomy.
2. Refactoring `app/chat.py` into stage modules.
3. Adding a typed tool registry + execution harness.
4. Building planner/executor/verifier orchestration.
5. Adding checkpointed task state and resumable runs.
6. Hardening USB behavior (rotation, atomic writes, FAT32-aware constraints).
7. Defining benchmarks and acceptance tests per release milestone.

If you want, next step can be a **v1.2 implementation PR** that starts with `--doctor`, structured logs, and pipeline extraction (highest impact, lowest risk).

# Sovereign Shards

Sovereign Shards is a local-first agent runtime that combines a deterministic tool pipeline with optional LLM reasoning.

## What is wired now

- Dynamic tool discovery from `tools/run/*.py`.
- Deterministic command routing (`run`, `read`, `write`, `status`, `help`, `exit`).
- Planner + executor pipeline with per-step results.
- Write verification for file operations.
- Optional LLM interpretation layered on top of tool output.

## Quick start

```bash
pip install -r requirements.txt
python run.py --doctor
python run.py
```

## Runtime command examples

```text
run python --version
read README.md
write notes.txt:hello world
status
help
exit
```

## Architecture (short)

1. Parse user intent.
2. Route intent to one or more tools.
3. Plan an `AgentTask`.
4. Execute via `HamiltonExecutor`.
5. Evaluate results (hook point).
6. Format output (and optional LLM reasoning).

## Key paths

- `app/chat.py` — orchestration loop.
- `app/agent/tool_registry.py` — external + built-in tool dispatch.
- `app/agent/executor.py` — plan execution and write verification.
- `tools/run/` — executable tool scripts.
- `MANUAL.md` — full user manual.

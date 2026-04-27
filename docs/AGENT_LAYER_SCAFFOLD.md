# Agent Layer Scaffold (Working Core)

This branch keeps the runtime lean and only includes currently working components plus next-step agent scaffolding.

## Included now

- Runtime chat loop (`app/chat.py`)
- Startup checks (`app/doctor.py`)
- Local server lifecycle (`app/local_server.py`)
- Session/runtime logs (`app/session.py`, `app/runtime_log.py`)
- Script-based tool primitives (`tools/run/read.py`, `write.py`, `exec.py`, `scaffold.py`)
- Agent contracts and tool registry bootstrap (`app/agent/*`)

## Agent wiring next

1. Planner emits `AgentStep` + `ToolCall` objects.
2. Executor validates every `ToolCall` against `ToolRegistry`.
3. Executor dispatches to `tools/run/*` wrappers.
4. Verifier records `ToolResult` and completion criteria.
5. Task state checkpointing persists `AgentTask` at each step.

## Guardrails scaffolded

- Required argument validation in `ToolRegistry.validate(...)`.
- Side-effect labels in `ToolSpec` for policy gating.
- Autonomy mode enum (`manual`, `semi`, `auto-safe`, `auto-full`) in `AgentTask`.

# Sovereign Shards User Manual

## 1) What this is
Sovereign Shards is a local-first coding/chat runtime that:
- starts a local `llama.cpp`-compatible model server,
- runs a natural-language terminal chat loop,
- can invoke local file/system tools when needed,
- logs every session transcript and metadata.

This manual is written for day-to-day operator use.

---

## 2) Quick start

### Requirements
- Python 3.10+
- Dependencies from `requirements.txt`
- Local model and binaries in expected paths (or configured by env vars)

### Install dependencies
```bash
python -m pip install -r requirements.txt
```

### Run interactive mode
```bash
python run.py
```

### Run one-shot mode
```bash
python run.py --message "Summarize repository status."
```

### Print local runtime paths
```bash
python run.py --paths
```

### Show where this manual lives
```bash
python run.py --manual
```

---

## 3) Interactive chat controls
Inside the chat loop:
- `quit` or `exit` → end session
- `/snapshot` → print system snapshot JSON
- `/help` → show command help
- `/tools` → show available tool API names
- `build <name> now` → fast-path scaffold via `run_scaffold` without waiting for model tool syntax

All normal text is treated as natural-language chat.

---

## 4) Tool invocation model
The assistant is *natural-language first*.
It should only invoke tools when needed to inspect or modify local files.

When it does use a tool, the assistant emits:

```text
ACTION:
{"tool": "read_file", "args": ["README.md"]}
```

Available tools include built-ins plus auto-discovered script tools from `tools/run/*.py`.

Built-ins:
- `read_file(path, offset=0, chunk_bytes=1048576)`
- `write_file(path, content, append=false)`
- `list_dir(path)`
- `system_snapshot()`

Script tools are exposed as `run_<script_name>` (example: `tools/run/read.py` -> `run_read`).

Script tool metadata (description + arg names) is read from `tools/run/registry.json` to improve tool selection and invocation quality.

Tool chaining is supported in a bounded loop to avoid hangs.
Built-in short breathers are inserted between tool steps to reduce sustained load on constrained hardware.

---

## 5) Session logs and artifacts

### Session logs
- Transcript: `logs/sessions/<session_id>.md`
- Metadata: `logs/sessions/<session_id>.json`

### Local model server logs
- Server startup/runtime log: `logs/server/<timestamp>.log`

Use these logs first when diagnosing issues.

---

## 6) Storage and chunking constraints
- Maximum file size enforced by tooling: **4GB** per file.
- Reads are chunk-oriented (default 1MB), with `offset` + `chunk_bytes` for sequential processing.
- Writes are blocked if they would exceed 4GB, matching FAT32-safe behavior for removable media constraints.

---

## 7) Environment configuration
Common env vars:
- `RUNTIME_BACKEND` (`llama_cpp` recommended default)
- `LLAMA_HOST`, `LLAMA_PORT`
- `LLAMA_MODEL_ALIAS`, `LLAMA_MODEL_PATH`
- `LLAMA_SERVER_BINARY`, `LLAMA_CLI_BINARY`
- `LLAMA_STARTUP_TIMEOUT`
- `OLLAMA_NUM_PREDICT`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_THREAD`, `OLLAMA_TEMPERATURE`

If relative paths are used, they are resolved from the repo root.

---

## 8) Troubleshooting

### "Missing server binary" or "Missing model file"
- Confirm paths with `python run.py --paths`
- Check env var overrides
- Verify files exist

### Local server times out on startup
- Inspect newest `logs/server/*.log`
- Increase `LLAMA_STARTUP_TIMEOUT`
- Lower context or thread settings if constrained

### Chat response stops unexpectedly
- Check server log for crash/OOM
- Retry in one-shot mode with shorter prompt

### Tool call output looks wrong
- Use `/tools` to verify tool names
- Ensure tool `args` is a JSON array

---

## 9) Operating best practices
- Keep prompts concise for deterministic local behavior.
- Ask for concrete edits and file paths when doing coding tasks.
- Use one-shot mode for scripts/automation.
- Keep session logs for reproducibility and audits.

---

## 10) "Production-ready" usage checklist
Before relying on this as your daily coding agent:
1. Validate model quality on your core repo tasks.
2. Confirm stable startup and shutdown behavior.
3. Test tool-based file edits in a disposable branch.
4. Verify session/server logs are captured.
5. Pin env vars for repeatable inference settings.

When these checks pass, operation should feel close to modern coding assistants while staying fully local.

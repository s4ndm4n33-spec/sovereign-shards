# Sovereign Shards User Manual

## 1) Install

```bash
pip install -r requirements.txt
```

## 2) Validate environment

```bash
python run.py --doctor
```

Expected checks:
- configuration
- tool registry
- disk health
- optional LLM server status

## 3) Start runtime

```bash
python run.py
```

## 4) Command syntax

### Execute shell
- `run <command>`
- `bash <command>`
- `execute <command>`
- `exec <command>`
- `cmd <command>`

### File read
- `read <path>`
- `cat <path>`
- `show <path>`

### File write
- `write <path>:<content>`
- `save <path>:<content>`
- `create <path>:<content>`

### Status and help
- `status` / `snapshot` / `health` / `check`
- `help` / `?` / `h`
- `exit` / `quit` / `q`

## 5) Tool wiring details

The registry scans `tools/run/*.py` at call time and dispatches by filename stem.

Examples:
- `tools/run/bash.py` -> tool name `bash`
- `tools/run/read.py` -> tool name `read`
- `tools/run/write.py` -> tool name `write`

Arguments are translated into CLI flags:
- scalar values: `--key value`
- list values: `--key v1 v2 ...`
- booleans: `--flag` only when true

## 6) Reliability behavior

- Write operations are atomic in `tools/run/write.py` (temp + replace).
- Executor verifies write persistence with retry/backoff.

## 7) Troubleshooting

- If tools are not found, confirm scripts exist in `tools/run/` and end with `.py`.
- If LLM is unavailable, runtime falls back to tool-only mode.
- Run `python run.py --doctor` before debugging deeper issues.

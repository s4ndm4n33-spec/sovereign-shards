# Option C Decomposed — J Fixes Its Own Auto-Reflection Bug

> **Context:** When J was given the full Option C prompt as a single message,
> it hallucinated a generic `chat.py` instead of reading the real one.
> The framework worked — J's reasoning couldn't hold the multi-step plan.
>
> This version decomposes the task into 4 atomic prompts. You (the user) are
> the planner. J is the hands. Feed these one at a time.

## Background

The bug: `working_memory.jsonl` grows to 35KB+ and never auto-shrinks.
The `/reflect` command compresses it manually, but there's no auto-trigger
after each turn. (Note: this may already be fixed — Session 19 added
auto-reflection. This test validates whether J can *discover* that.)

## The 4 Prompts

Feed each one to J as a separate turn. Wait for J to finish before
sending the next.

### Prompt 1 — Search

```
run_search should_reflect app/chat.py
```

**Expected:** Router handles this directly (zero inference). J sees grep
results showing where `should_reflect()` is called in chat.py.

**What to watch:** Does the router return real line numbers and context?

### Prompt 2 — Read the Relevant Section

After seeing the search results, ask J to read around that area:

```
run_read app/chat.py
```

**Expected:** Router handles this. J sees the actual chat.py code.
At 2048 tokens this will be truncated — J should see enough of the main
loop to understand the structure.

**Alternative** (if the file is too long):
```
run_search "weight-triggered reflection" app/chat.py
```

### Prompt 3 — Analyze and Plan

Now J has seen the code. Ask it to reason:

```
Based on what you just read, is there already auto-reflection code in
chat.py? If yes, describe where it is and what triggers it. If no,
describe exactly where it should be added (which function, after which
line) and what the code should look like.
```

**Expected:** J should identify the existing `if should_reflect():`
block near the end of the main loop. This is a pure reasoning turn
(budget=0, no tools needed).

**What to watch:** Does J recognize the existing code? Or does it
hallucinate something new? This is the reasoning test.

### Prompt 4 — Write the Fix (or Confirm)

If J correctly identified the existing auto-reflection:

```
Good. The auto-reflection is already wired in. Now check: does it also
fire after router-handled turns? Search for "compress_turn" to see
where working memory gets updated for routed commands.
```

If J missed it and proposed adding new code:

```
Look more carefully at the code after _run_turn() is called in the
main while True loop. There is already a should_reflect() check.
Read those lines again.
```

**Expected:** J searches for `compress_turn` and finds it's called in
two places: (1) inside `_run_turn` for LLM-handled turns, and (2) in
the main loop for router-handled turns. But auto-reflection only fires
after LLM turns, not after router turns. This is the *actual* remaining
bug.

## Scoring

| Step | Criteria | PASS/FAIL |
|------|----------|-----------|
| 1 | Router returns real grep results | |
| 2 | J sees actual chat.py code | |
| 3 | J correctly identifies existing auto-reflection (or proposes accurate fix) | |
| 4 | J finds the router-turn gap (auto-reflect missing after routed commands) | |

**4/4 = J can engineer with decomposed steps**
**3/4 = J can read and reason but misses edge cases**
**≤2/4 = Still needs more framework support**

## Using the `/steps` Command

You can also load these as a plan into the task buffer:

```
/steps
1. run_search should_reflect app/chat.py
2. run_read app/chat.py
3. Analyze: is there already auto-reflection code? Where is it? What triggers it?
4. Check: does auto-reflection fire after router-handled turns too?
```

The buffer-based executor will feed each step to J with a clean context.

## What This Tests

- **Step 1-2:** Framework competency (router, tools) — should pass trivially
- **Step 3:** Reasoning from code — can J understand code it just read?
- **Step 4:** Edge case detection — can J find a real bug with guidance?

If a bigger model (14B, 32B) passes step 3-4 where 7B fails, the gap is
purely reasoning. The task buffer still helps because it keeps each step
clean, but the model upgrade would unlock real engineering capability.

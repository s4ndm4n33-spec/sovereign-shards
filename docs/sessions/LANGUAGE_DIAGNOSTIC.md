# J Language Issue — Diagnostic & Fix Log

> J responds in Chinese (你好！有什么我可以帮忙的吗？) instead of English on first interaction.

**Model:** Qwen2.5-Coder-7B-Instruct Q4_K_M  
**Hardware:** 16 GB RAM, 2048 token context  
**Last updated:** 2026-05-07

---

## Root Cause Analysis

Qwen2.5 is a bilingual model (Chinese/English). Without an explicit English instruction in the system prompt, it defaults to Chinese — especially for short or ambiguous inputs like "hello" or "hi".

The issue has **three compounding factors:**

### Factor 1: Old system prompt was too large for 2048 context

The original `J-system.txt` was ~3072 chars (~768 tokens). On top of that, `build_history()` injected:
- Full tool descriptions: ~900 tokens
- Hardware context: ~125 tokens  
- **Total system message: ~1793 tokens**

At 2048 context with `num_predict=1024`, `preflight_trim` only has a budget of **1024 tokens**. The 1793-token system message triggers Stage 3 (emergency trim), which caps system at 60% of budget = ~614 tokens ≈ 2456 chars. The "Always respond in English" instruction and Identity Lock were at the END of the prompt — they got truncated.

**Status:** Fixed in commit `f123873` (slim prompt, 279 tokens). Tool descriptions and hardware context removed from `build_history()`.

### Factor 2: `num_predict` default is too high

`client.py` defaults `num_predict` to 1024 if not set in `.env`. At 2048 context, this means:
- Budget = 2048 - 1024 = 1024 tokens for the entire conversation
- Only 745 tokens left after system prompt (279 tokens)
- After ONE user message + ONE assistant reply, you're already in trim territory

**Status:** Clean `.env` was provided with `num_predict=256`. But if the user's `.env` still has the old default, this kicks in. Fixed in this commit — `client.py` now auto-clamps `num_predict` to max 25% of `num_ctx` for small contexts.

### Factor 3: Memory injection can balloon the system message

`reconstruct_context()` merges working memory and long-term memory INTO the system message. On subsequent sessions (where memory files exist from previous runs), this can add hundreds of tokens to the system message, pushing it over budget and triggering truncation.

**Status:** Fixed in this commit — `reconstruct_context()` now caps memory injection to 30% of the context budget.

---

## What Was Tried (Chronological)

| # | What | Commit | Result |
|---|------|--------|--------|
| 1 | Added "Always respond in English" to voice line in J-system.txt | `42c9578` | Untested — user ran old code before pulling |
| 2 | Added Identity Lock at end of J-system.txt ("You are J. NOT Qwen...") | `42c9578` | Identity Lock gets truncated at 2048 context with old prompt |
| 3 | Slimmed J-system.txt from 3072→1118 chars (~279 tokens) | `f123873` | Should fix it — but user needs to `git pull` |
| 4 | Removed tool descriptions from build_history() | `f123873` | Reduces system message from ~1793 to ~279 tokens |
| 5 | Added startup diagnostics (token count, prompt preview) | `42c9578` | Lets user verify correct prompt loaded |
| 6 | Moved "English" to first line of J-system.txt | This commit | Survives any truncation — first line is never cut |
| 7 | Auto-clamp num_predict to 25% of context for small windows | This commit | Prevents budget starvation |
| 8 | Cap memory injection to 30% of context budget | This commit | Prevents memory from crowding out identity |
| 9 | Added non-English response detection + warning | This commit | User sees diagnostic if language drift occurs |

---

## Current Fix (This Commit)

### Fix A: English instruction as first line of system prompt

Moved "Always respond in English" from the Identity Lock section (end of prompt) to the very first sentence. On any truncation stage, the beginning of the prompt is preserved. The end is what gets cut.

**Before:**
```
You are J — a sovereign developer agent...
Voice: calm, precise, sardonic...
...
IDENTITY LOCK: You are J. NOT Qwen... Always respond in English.
```

**After:**
```
Always respond in English. You are J — a sovereign developer agent...
Voice: calm, precise, sardonic...
...
IDENTITY LOCK: You are J. NOT Qwen. Never reference Qwen or Alibaba. Every response is from J.
```

### Fix B: Smart num_predict default

`client.py` now auto-clamps: if `num_ctx <= 2048` and `num_predict > num_ctx // 4`, it reduces `num_predict` to `num_ctx // 4` (= 512 at 2048 context). This ensures at least 75% of context is available for the conversation.

### Fix C: Memory injection cap

`reconstruct_context()` now limits the injected memory block to 30% of `max_tokens`. If memory exceeds this, it takes fewer entries until it fits. This prevents accumulated memory from crowding out the system prompt or conversation.

### Fix D: Non-English response detection

After each LLM response, if the first 50 characters contain non-ASCII characters (CJK range), a warning is printed:

```
⚠ LANGUAGE DRIFT: Response may not be in English. Check system prompt and .env.
  System prompt: 279 tokens | Context budget: 1792 tokens
```

This gives the user (and any future debugger) immediate visibility into the issue.

---

## Remaining Risks

1. **User hasn't pulled latest code.** All fixes require `git pull origin main`. If the user is still on the old commit, none of this applies.

2. **Jinja template not loading.** If `J-chat-template.jinja` fails to load, llama.cpp falls back to its built-in ChatML template. The `J: ` generation prefix (which reinforces identity) would be lost. The startup diagnostics don't check this.

3. **Model quantization artifacts.** At Q4_K_M, some instruction-following capability is lost. The 7B model may simply ignore the English instruction on ambiguous inputs. Not much we can do about this beyond making the instruction more prominent (which we've done).

4. **Context pressure after 5+ turns.** Even with all fixes, at 2048 context, the model only has ~15 turns of history before aggressive trimming kicks in. The system prompt survives, but the model may lose coherence with so little conversation context.

---

## How to Verify the Fix

After pulling latest code:

```
cd "E:\dev shard"
git fetch origin
git reset --hard origin/main
```

Then launch:

```
run-shard.bat
```

**Check the startup banner:**
```
Context: 2048 tokens (budget 1536, system ~285)
Prompt:  Always respond in English. You are J — a sovereign...
```

If you see:
- `budget` ≥ 1500 → `num_predict` is properly clamped
- `system ~280-290` → slim prompt is loaded
- `Prompt: Always respond in English...` → correct J-system.txt is active

**Test with:**
```
You: hello
```

Expected: J responds in English with sardonic personality.

If J responds in Chinese/Japanese:
1. Check the startup banner for the values above
2. Check `.env` — ensure `OLLAMA_NUM_PREDICT` is 256 or absent
3. Check `prompts/J-system.txt` — first line should say "Always respond in English"
4. Check server log in `logs/server/` — look for template loading errors

---

## Nuclear Option (If All Else Fails)

If the 7B model simply won't follow the English instruction reliably:

1. **Try Qwen2.5-Coder-3B.** Smaller, but actually better at instruction-following per token because less capacity is wasted on Chinese knowledge.

2. **Try a monolingual model.** CodeLlama-7B, Phi-3-mini, or StarCoder2-7B are English-only. No Chinese language capability = no Chinese output.

3. **Post-process in the chat loop.** Add a language detector after each response. If non-English, retry with "Respond in English only: " prepended to the user message. Costs one extra inference call but guarantees English.

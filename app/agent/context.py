# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Context window budget management.

Keeps the conversation within token limits by summarizing old turns.
Estimates tokens as chars/4 (good enough for local models).

Includes a pre-flight budget gate so no request ever exceeds the
server's context window, and a step compressor for seaming multi-step
workflows across context boundaries.
"""

from __future__ import annotations
import json
import time
from pathlib import Path

# Conservative default for small local models on USB hardware
DEFAULT_MAX_TOKENS = 4096
CHARS_PER_TOKEN = 4  # rough estimate
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCRATCH_PAD_PATH = BASE_DIR / "memory" / "scratch_pad.jsonl"


def estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    """Estimate total tokens across all messages."""
    return sum(estimate_tokens(m.get("content", "")) for m in messages)


def trim_context(
    messages: list[dict[str, str]],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    keep_system: bool = True,
    keep_last_n: int = 4,
) -> list[dict[str, str]]:
    """Trim conversation to fit within token budget.

    Strategy:
    1. Always keep system message(s) at the front.
    2. Always keep the last N messages.
    3. Summarize/drop middle messages until we fit.
    """
    if not messages:
        return messages

    total = estimate_messages_tokens(messages)
    if total <= max_tokens:
        return messages

    # Split into system, middle, and tail
    system_msgs = []
    rest = []
    for m in messages:
        if m.get("role") == "system" and keep_system and not rest:
            system_msgs.append(m)
        else:
            rest.append(m)

    if len(rest) <= keep_last_n:
        return messages  # can't trim further without losing recent context

    tail = rest[-keep_last_n:]
    middle = rest[:-keep_last_n]

    _extract_middle_tool_facts(middle)

    # Compress middle into a single summary message
    summary_parts = []
    for m in middle:
        role = m.get("role", "?")
        content = m.get("content", "")
        # Take first 200 chars of each message
        snippet = content[:200].replace("\n", " ")
        if len(content) > 200:
            snippet += "..."
        summary_parts.append(f"[{role}] {snippet}")

    summary = "[CONTEXT SUMMARY — older messages compressed]\n" + "\n".join(summary_parts)
    summary_msg = {"role": "system", "content": summary}

    result = system_msgs + [summary_msg] + tail
    result.append(
        {
            "role": "system",
            "content": "[SCRATCH PAD] Previously extracted data saved at memory/scratch_pad.jsonl. Use run_read to access if needed.",
        }
    )

    # If still too big, just keep system + tail
    if estimate_messages_tokens(result) > max_tokens:
        result = system_msgs + tail

    return result


def _extract_middle_tool_facts(middle: list[dict[str, str]]) -> None:
    """Persist key tool-output data before middle-message compression."""
    if not middle:
        return
    SCRATCH_PAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SCRATCH_PAD_PATH.open("a", encoding="utf-8") as handle:
        for m in middle:
            content = m.get("content", "")
            if "[TOOL EXECUTION]" not in content:
                continue
            tool = ""
            args: list[str] = []
            result = ""
            for line in content.splitlines():
                if line.startswith("tool:"):
                    tool = line.split(":", 1)[1].strip()
                elif line.startswith("args:"):
                    raw = line.split(":", 1)[1].strip()
                    try:
                        parsed = json.loads(raw.replace("'", '"'))
                        if isinstance(parsed, list):
                            args = [str(x) for x in parsed]
                    except Exception:
                        args = [raw]
            if "result:\n" in content:
                result = content.split("result:\n", 1)[1]
            elif "result:" in content:
                result = content.split("result:", 1)[1]
            key_data = result[:4000]
            entry = {"tool": tool, "args": args, "key_data": key_data, "ts": time.time()}
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Pre-flight budget gate ─────────────────────────────────────────


def preflight_trim(
    messages: list[dict[str, str]],
    max_ctx: int,
    reserve_for_reply: int = 1024,
) -> list[dict[str, str]]:
    """Hard budget gate — called right before every LLM request.

    Ensures the outbound payload fits in (max_ctx - reserve_for_reply)
    so the server never rejects the request and the model has room to
    actually generate a response.

    Three escalation stages:
      1. Normal trim (summarize middle messages).
      2. Aggressive trim (cap every message, keep fewer tails).
      3. Emergency trim (system + last 2 messages only).
    """
    # 10% safety margin accounts for tokenizer estimation drift
    safety_margin = max(64, int(max_ctx * 0.10))
    budget = max(256, max_ctx - reserve_for_reply - safety_margin)
    current = estimate_messages_tokens(messages)

    if current <= budget:
        return messages

    # Stage 1: normal trim
    messages = trim_context(messages, max_tokens=budget)
    if estimate_messages_tokens(messages) <= budget:
        return messages

    # Stage 2: aggressive — cap non-system content, fewer tail messages
    messages = trim_context(messages, max_tokens=budget, keep_last_n=2)
    if estimate_messages_tokens(messages) <= budget:
        return messages

    # Stage 3: hard compress everything
    result = []
    for m in messages:
        content = m.get("content", "")
        if m.get("role") == "system":
            # Cap system prompt at 60% of budget
            sys_cap = int(budget * 0.6 * CHARS_PER_TOKEN)
            if len(content) > sys_cap:
                content = content[:sys_cap] + "\n[...truncated to fit context window...]"
            result.append({"role": "system", "content": content})
        else:
            # Cap each turn at ~150 tokens
            turn_cap = 150 * CHARS_PER_TOKEN
            if len(content) > turn_cap:
                content = content[:turn_cap] + "..."
            result.append({"role": m["role"], "content": content})

    # If STILL over, last resort: system + last 2 messages
    if estimate_messages_tokens(result) > budget:
        system = [m for m in result if m.get("role") == "system"]
        non_system = [m for m in result if m.get("role") != "system"]
        result = system + non_system[-2:]

    return result


# ── Step compressor for multi-step seaming ─────────────────────────


def compress_step_result(
    step_id: str,
    goal: str,
    reply: str,
    passed: bool,
) -> str:
    """Compress a completed step into a single-line working memory entry.

    Used after each agent step so the next step starts with a clean
    context instead of dragging the full conversation forward.
    """
    status = "DONE" if passed else "FAILED"
    # Extract the first meaningful line from the reply
    lines = [l.strip() for l in reply.strip().splitlines() if l.strip()]
    snippet = lines[0][:200] if lines else "(no output)"
    return f"[{status}] {step_id}: {goal} → {snippet}"


# ── Tier 1: Active Context Reconstruction ──────────────────────────


def reconstruct_context(
    messages: list[dict[str, str]],
    task_hint: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[dict[str, str]]:
    """Assemble active context from all three memory tiers.

    1. Keep the system message (tools, persona) as a single atomic block.
    2. Inject relevant *working memory* entries (Tier 2) via BM25.
    3. Inject relevant *long-term memory* entries (Tier 3) via BM25.
    4. Memory is merged INTO the system message — never a separate message.
    5. Keep recent conversation messages.
    6. Trim to fit the token budget.
    """
    from app.agent import working_memory
    from app.agent.memory import recall_all
    from app.agent.retriever import retrieve

    # -- Tier 2: Working memory (recent steps / decisions) --
    wm_entries = working_memory.read_all()
    if wm_entries and task_hint:
        wm_relevant = retrieve(task_hint, wm_entries, top_k=8)
    else:
        wm_relevant = wm_entries[-8:]

    # -- Tier 3: Long-term memory (learned facts / tools) --
    lt_data = recall_all()
    lt_chunks = [{"key": k, "text": v} for k, v in lt_data.items()]
    if lt_chunks and task_hint:
        lt_relevant = retrieve(task_hint, lt_chunks, top_k=5)
    else:
        lt_relevant = lt_chunks[:5]

    # -- Build the memory injection block --
    sections: list[str] = []
    if wm_relevant:
        sections.append(working_memory.format_for_context(wm_relevant))
    if lt_relevant:
        lt_lines = ["[LONG-TERM MEMORY]"]
        for c in lt_relevant:
            lt_lines.append(f"• {c.get('key', '?')}: {c.get('text', '?')}")
        sections.append("\n".join(lt_lines))

    if not sections:
        return trim_context(messages, max_tokens=max_tokens)

    mem_block = "\n\n".join(sections)

    # ── Cap memory injection to 30% of context budget ──────────────
    # On small context windows the system prompt must stay intact.
    # If memory is too large, trim entries until it fits.
    mem_cap = int(max_tokens * 0.30 * CHARS_PER_TOKEN)
    if len(mem_block) > mem_cap:
        mem_block = mem_block[:mem_cap] + "\n[...memory trimmed to fit budget...]"

    # Merge memory INTO the first system message so trim_context never
    # drops J's identity.  System messages are always preserved.
    injected = list(messages)
    if injected and injected[0].get("role") == "system":
        injected[0] = {
            "role": "system",
            "content": injected[0]["content"] + "\n\n" + mem_block,
        }
    else:
        # No system message at front — prepend one
        injected.insert(0, {"role": "system", "content": mem_block})

    return trim_context(injected, max_tokens=max_tokens)

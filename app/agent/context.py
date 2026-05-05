"""Context window budget management.

Keeps the conversation within token limits by summarizing old turns.
Estimates tokens as chars/4 (good enough for local models).
"""

from __future__ import annotations

# Conservative default for small local models on USB hardware
DEFAULT_MAX_TOKENS = 4096
CHARS_PER_TOKEN = 4  # rough estimate


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

    # If still too big, just keep system + tail
    if estimate_messages_tokens(result) > max_tokens:
        result = system_msgs + tail

    return result


# ── Tier 1: Active Context Reconstruction ──────────────────────────


def reconstruct_context(
    messages: list[dict[str, str]],
    task_hint: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[dict[str, str]]:
    """Assemble active context from all three memory tiers.

    1. Keep the system message (tools, persona).
    2. Inject relevant *working memory* entries (Tier 2) via BM25.
    3. Inject relevant *long-term memory* entries (Tier 3) via BM25.
    4. Keep recent conversation messages.
    5. Trim to fit the token budget.
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
    mem_msg: dict[str, str] = {"role": "system", "content": mem_block}

    # Insert memory block right after the first system message
    injected = list(messages)
    insert_at = 0
    for i, m in enumerate(injected):
        if m.get("role") != "system":
            insert_at = i
            break
    else:
        insert_at = len(injected)
    injected.insert(insert_at, mem_msg)

    return trim_context(injected, max_tokens=max_tokens)

"""Weight-triggered self-reflection: consolidate working memory.

Fires ONLY when working_memory.jsonl exceeds its size threshold.
Asks the LLM to compress N entries into fewer, tighter summaries.
"""

from __future__ import annotations

import json
import re

from app.agent import working_memory

REFLECT_PROMPT = (
    "You are a memory compressor. Below are {n} working memory entries "
    "from a coding session.\n"
    "Consolidate them into at most {target} entries. Preserve:\n"
    "- Key decisions and their reasons\n"
    "- Errors encountered and how they were resolved\n"
    "- Important discoveries about the codebase\n"
    "- Current state of the task\n"
    "Drop: routine tool calls, redundant steps, verbose output details.\n\n"
    "Entries:\n{entries}\n\n"
    "Respond with ONLY a JSON array of objects, each with: "
    "step, result, and optionally issue and decision.\n"
    "No prose, no markdown fences."
)


def build_reflect_prompt(entries: list[dict], target: int = 5) -> str:
    """Build the reflection/compression prompt."""
    formatted = json.dumps(entries, indent=1, ensure_ascii=False)
    return REFLECT_PROMPT.format(n=len(entries), target=target, entries=formatted)


def parse_reflected(raw: str) -> list[dict]:
    """Parse LLM reflection output back into memory entries."""
    cleaned = re.sub(r"```json?\s*", "", raw)
    cleaned = re.sub(r"```", "", cleaned).strip()

    match = re.search(r"\[.*\]", cleaned, flags=re.S)
    if not match:
        return []

    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    if not isinstance(items, list):
        return []

    valid: list[dict] = []
    for item in items:
        if isinstance(item, dict) and "step" in item and "result" in item:
            entry: dict = {"step": item["step"], "result": item["result"]}
            if item.get("issue"):
                entry["issue"] = item["issue"]
            if item.get("decision"):
                entry["decision"] = item["decision"]
            valid.append(entry)
    return valid


def should_reflect() -> bool:
    """True when working memory has crossed the weight threshold."""
    return working_memory.needs_reflection()


def apply_reflection(consolidated: list[dict]) -> None:
    """Replace working memory with consolidated entries."""
    working_memory.replace_entries(consolidated)

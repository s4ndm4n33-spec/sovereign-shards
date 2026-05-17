# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tool researcher: analyse a capability gap and produce a tool spec.

When the planner detects a request that no existing tool can satisfy,
the researcher decomposes the domain and outputs a structured spec
that the forge uses to generate code.

Zero external deps.  Pure prompt engineering + JSON parsing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from app.agent.retriever import retrieve
    from app.agent.tool_registry import ToolRegistry


# ── Data ─────────────────────────────────────────────────

@dataclass
class ToolSpec:
    """Blueprint for a tool the forge will generate."""
    tool_name: str
    purpose: str
    inputs: list[str] = field(default_factory=list)        # ["path: str", "depth: int"]
    outputs: list[str] = field(default_factory=list)       # ["path to file"]
    dependencies: list[str] = field(default_factory=list)  # flagged, not auto-installed
    companion_tools: list[str] = field(default_factory=list)
    example_call: str = ""                                  # e.g. run_stl_plan("cube", "out.stl")


@dataclass
class ResearchResult:
    """Output of the research phase."""
    intent: str                          # cleaned user intent
    specs: list[ToolSpec]                # one or more tools to build
    local_hits: list[dict] = field(default_factory=list)  # BM25 matches
    reasoning: str = ""                  # model's domain breakdown


# ── Prompts ──────────────────────────────────────────────

RESEARCH_PROMPT = """\
You are a tool architect.  The user needs a capability that doesn't exist yet.

Existing tools:
{tool_listing}

Local code matches (may be useful):
{local_hits}

User request: {request}

Break the request into one or more new tools.  For EACH tool produce:
{{
  "tool_name": "short_snake_case",
  "purpose": "one sentence",
  "inputs": ["arg_name: type", ...],
  "outputs": ["what it returns"],
  "dependencies": ["any pip packages NOT in stdlib — empty if none"],
  "companion_tools": ["other new tool names this one works with"],
  "example_call": "run_tool_name(\\"arg1\\", \\"arg2\\")"
}}

Rules:
- Prefer stdlib.  Flag ANY non-stdlib dep in "dependencies".
- tool_name MUST start with a lowercase letter, snake_case only.
- If the task needs multiple tools, list them all as a JSON array.
- Keep each tool single-purpose.

Respond with ONLY a JSON array.  No prose, no markdown fences.
"""


# ── Detection ────────────────────────────────────────────

# Explicit trigger phrases
_FORGE_TRIGGERS = re.compile(
    r"(build|create|make|write|generate|add)\s+(a\s+)?(tool|script|command|utility)\s+(for|that|to)\b",
    re.IGNORECASE,
)


def needs_new_tool(
    request: str,
    registry: "ToolRegistry",
) -> bool:
    """Fast check: does this request imply a capability J lacks?

    Returns True if:
    1. Explicit trigger phrase ("build a tool for X"), OR
    2. No existing tool name appears anywhere in the request
       (heuristic — planner can override later)
    """
    # 1. Explicit
    if _FORGE_TRIGGERS.search(request):
        return True

    # 2. Heuristic: if the request mentions none of our tool names,
    #    it *might* need a new one.  This is a soft signal — the planner
    #    should use the model as final arbiter when this returns True.
    lower = request.lower()
    tool_names = list(registry.specs.keys())
    if not any(name.replace("run_", "") in lower for name in tool_names):
        return True

    return False


# ── Research pipeline ────────────────────────────────────

def build_research_prompt(
    request: str,
    tool_listing: str,
    local_hits: list[dict],
) -> str:
    """Build the prompt sent to the model for tool spec generation."""
    hit_text = ""
    if local_hits:
        for h in local_hits[:5]:
            score = h.get("_score", 0)
            text = " ".join(v for k, v in h.items()
                            if isinstance(v, str) and k != "_score")[:200]
            hit_text += f"  [{score:.1f}] {text}\n"
    else:
        hit_text = "  (none)\n"

    return RESEARCH_PROMPT.format(
        tool_listing=tool_listing,
        local_hits=hit_text.strip(),
        request=request,
    )


def parse_research(raw: str, request: str) -> ResearchResult:
    """Parse model output into a ResearchResult."""
    specs = _try_parse_specs(raw)
    if not specs:
        # Fallback: single generic spec from the request
        name = _slugify(request)
        specs = [ToolSpec(
            tool_name=name,
            purpose=request[:120],
            inputs=["input: str"],
            outputs=["result string"],
        )]

    return ResearchResult(
        intent=request,
        specs=specs,
        reasoning=raw,
    )


def _try_parse_specs(raw: str) -> list[ToolSpec]:
    """Extract JSON array of tool specs from model output."""
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

    specs: list[ToolSpec] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("tool_name", "")
        if not name or not re.match(r"^[a-z][a-z0-9_]*$", name):
            continue
        specs.append(ToolSpec(
            tool_name=name,
            purpose=item.get("purpose", ""),
            inputs=item.get("inputs", []),
            outputs=item.get("outputs", []),
            dependencies=item.get("dependencies", []),
            companion_tools=item.get("companion_tools", []),
            example_call=item.get("example_call", ""),
        ))
    return specs


def _slugify(text: str) -> str:
    """Best-effort slug from free text."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    slug = slug.strip("_")[:30]
    return slug or "custom_tool"

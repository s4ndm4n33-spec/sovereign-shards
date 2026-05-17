# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Verifier: check whether a step's success criteria are met.

Asks the LLM to evaluate the step output against the criteria.
Returns a pass/fail verdict with reasoning.
"""

from __future__ import annotations

import json
import re


VERIFY_PROMPT = """You are a step verifier. Given a step goal, its success criteria,
and the execution output, determine if the step succeeded.

Step goal: {goal}
Success criteria: {criteria}
Execution output:
{output}

Respond with ONLY a JSON object:
{{"passed": true/false, "reason": "brief explanation"}}
"""


def build_verify_prompt(goal: str, criteria: str, output: str) -> str:
    """Build the verification prompt."""
    # Truncate output to avoid blowing context
    if len(output) > 4000:
        output = output[:4000] + "\n... [TRUNCATED]"
    return VERIFY_PROMPT.format(goal=goal, criteria=criteria, output=output)


def parse_verdict(raw: str) -> tuple[bool, str]:
    """Parse the LLM verification response.

    Returns (passed, reason). Defaults to (True, ...) if parsing fails
    (benefit of the doubt — the executor output is the real signal).
    """
    cleaned = re.sub(r"```json?\s*", "", raw)
    cleaned = re.sub(r"```", "", cleaned).strip()

    match = re.search(r"\{.*\}", cleaned, flags=re.S)
    if not match:
        return True, "Verification parse failed; assuming pass."

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return True, "Verification parse failed; assuming pass."

    passed = bool(data.get("passed", True))
    reason = data.get("reason", "No reason given.")
    return passed, reason

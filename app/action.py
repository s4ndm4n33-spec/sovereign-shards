"""Action parsing and tool output formatting.

Extracts ACTION payloads from model responses and formats tool output
for LLM consumption.
"""

import ast
import re
from json import JSONDecodeError, loads

MAX_TOOL_OUTPUT_LINES = 60  # truncate tool output to protect 2048 context


def _balanced_json(text: str, start: int) -> str | None:
    """Extract the first balanced JSON object from *text* starting at *start*.

    Counts braces outside of string literals so nested objects (e.g.
    run_str_replace payloads) are handled correctly.  Returns ``None``
    if no balanced object is found.
    """
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_action(content: str) -> dict | None:
    """Parse an ACTION payload from the model response.

    Handles three formats J may produce:
      1. ACTION:{"tool": "...", "args": [...]}     (standard JSON)
      2. ACTION:tool_name arg1 arg2                (bare / no-JSON)
      3. ACTION:{...} [TOOL EXECUTION] ...         (hallucinated tail)
    """
    if "ACTION:" not in content:
        return None

    payload = content.split("ACTION:", 1)[1].strip()
    if not payload:
        return None

    # Strip hallucinated [TOOL …] blocks that J sometimes appends
    for marker in ("[TOOL EXECUTION]", "[TOOL"):
        idx = payload.find(marker)
        if idx > 0:
            payload = payload[:idx].rstrip()

    # ── 1. Try balanced-brace JSON extraction ───────────────────────
    brace = payload.find("{")
    if brace != -1:
        json_str = _balanced_json(payload, brace)
        if json_str:
            try:
                return loads(json_str)
            except JSONDecodeError:
                try:
                    return ast.literal_eval(json_str)
                except Exception:
                    pass

    # ── 2. Regex rescue: extract tool + args from broken JSON ────────
    # Models (especially 7B) sometimes produce JSON with unescaped
    # quotes inside string values — e.g. regex patterns like [^"]+.
    # json.loads and literal_eval both choke, but we can still pull
    # the tool name and reconstruct args with regex.
    if brace != -1:
        raw = json_str or payload
        tool_m = re.search(r'"tool"\s*:\s*"(\w+)"', raw)
        if tool_m:
            tool = tool_m.group(1)
            # Try to extract args from the broken JSON.
            # Strategy: find the last cleanly-quoted path arg (always
            # simple alphanumerics/slashes), then everything between
            # the first arg quote and that delimiter is the first arg.
            last_simple = re.search(
                r',\s*"([a-zA-Z0-9_./ -]+)"\s*\]', raw
            )
            if last_simple:
                path = last_simple.group(1)
                # Locate the first arg between "args": [" and ,
                arr_pos = raw.find('"args"')
                if arr_pos >= 0:
                    bracket = raw.find("[", arr_pos)
                    if bracket >= 0:
                        # first_arg is everything between [" and ",
                        first_raw = raw[bracket + 2 : last_simple.start()]
                        first_raw = first_raw.rstrip('"').strip()
                        first_arg = first_raw.replace('\\"', '"')
                        return {"tool": tool, "args": [first_arg, path]}
                return {"tool": tool, "args": [path]}
            return {"tool": tool, "args": []}

    # ── 3. Bare fallback: ACTION:tool_name arg1 arg2 (no JSON) ─────
    parts = payload.split(None, 1)
    if parts and re.match(r"^[a-z_][a-z0-9_]*$", parts[0]):
        tool = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        args = rest.split() if rest else []
        return {"tool": tool, "args": args}

    return None


def strip_identity_preamble(text: str) -> str:
    """Strip leaked identity preambles before tool/action parsing."""
    cleaned = re.sub(r"^\s*I am J[,.].*?(?:\n\n|\n)", "", text, flags=re.IGNORECASE | re.S)
    marker = cleaned.find("ACTION:")
    if marker > 0:
        prefix = cleaned[:marker]
        if "I am J" in prefix:
            cleaned = cleaned[marker:]
    return cleaned.strip()


def truncate_tool_output(output: str, max_lines: int = MAX_TOOL_OUTPUT_LINES) -> str:
    """Truncate large tool output to protect the 2048 context window.

    Keeps the first and last lines so J sees structure and end-state,
    with a hint to use run_search for specifics.
    """
    lines = output.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return output
    head_n = max_lines - 5  # most context at the top
    tail_n = 5
    head = "".join(lines[:head_n])
    tail = "".join(lines[-tail_n:])
    omitted = len(lines) - head_n - tail_n
    return (
        f"{head}"
        f"\n[... {omitted} lines omitted — use run_search to find specific content ...]\n"
        f"{tail}"
    )

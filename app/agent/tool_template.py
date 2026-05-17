# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Tool template: canonical structure for auto-generated tools.

This module exists purely as documentation and for the forge to reference.
Every tool in tools/run/ follows this contract — hand-written or generated.
"""

TEMPLATE = '''\
"""Auto-generated tool: {purpose}

Built by J's tool forge.  Follows the standard tool contract:
TOOL_NAME, TOOL_DESC, and a run() function that returns a string.
"""

import os
import sys

TOOL_NAME = "run_{tool_name}"
TOOL_DESC = """{purpose}"""


def run({args}) -> str:
    """{purpose}

    Args:
{arg_docs}
    Returns:
        Result string.
    """
    # --- implementation goes here ---
    return "[OK] Done"


# ── CLI entry point (tools/run convention) ───────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        print(run(*args))
    except Exception as exc:
        print(f"[TOOL ERROR] {{exc}}")
        sys.exit(1)
'''


# ── Contract rules (referenced by forge prompts) ────────

CONTRACT = """
TOOL CONTRACT — every tools/run/*.py file must satisfy:

1. TOOL_NAME = "run_<name>"     # auto-discovery key
2. TOOL_DESC = "..."            # one-line description
3. def run(...) -> str:         # main entry, returns string
4. CLI: if __name__ == "__main__" reads sys.argv, calls run(), prints result
5. Errors: return "[TOOL ERROR] ..." — never raise to caller
6. No network calls unless explicitly authorised
7. No interactive input (stdin OK for piped data only)
8. Timeout: default 30s — long ops should stream progress
"""

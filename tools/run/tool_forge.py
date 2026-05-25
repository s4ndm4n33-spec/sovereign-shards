# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Auto-generated tool: Generate new tool script

Built by J's tool forge.  Follows the standard tool contract:
TOOL_NAME, TOOL_DESC, and a run() function that returns a string.
"""

import sys

TOOL_NAME = "run_tool_forge"
TOOL_DESC = """Generate new tool script"""


def run(name, purpose, inputs, outputs, dependencies):
    try:
        if not isinstance(inputs, list) or not all(isinstance(i, str) for i in inputs):
            raise ValueError("Invalid inputs")
        if not isinstance(outputs, list) or not all(isinstance(o, str) for o in outputs):
            raise ValueError("Invalid outputs")
        if not isinstance(dependencies, list) or not all(
            isinstance(d, str) for d in dependencies
        ):
            raise ValueError("Invalid dependencies")

        input_lines = "".join(
            f"        {item} = input('Enter {item}: ') or None\n" for item in inputs
        )

        return f"""# tool_forge script

# Name: {name}
# Purpose: {purpose}

def get_{name}():
    try:
        # Get inputs
{input_lines}
        # Process inputs
        {purpose}

        # Return outputs
        return {", ".join(outputs)}
    except Exception as e:
        print(f"Error: {{e}}")
        return None


if __name__ == "__main__":
    print(get_{name}())
"""
    except Exception as e:
        return f"[TOOL ERROR] Failed to generate script: {str(e)}"


def get_inputs():
    return input("Enter inputs (comma-separated): ").split(",")


def get_outputs():
    return input("Enter outputs (comma-separated): ").split(",")


def get_dependencies():
    return input("Enter dependencies (comma-separated): ").split(",")


# ── CLI entry point (tools/run convention) ───────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        print(run(*args))
    except Exception as exc:
        print(f"[TOOL ERROR] {exc}")
        sys.exit(1)

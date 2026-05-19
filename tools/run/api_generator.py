# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Auto-generated tool: Generate REST API endpoints from a schema

Built by J's tool forge.  Follows the standard tool contract:
TOOL_NAME, TOOL_DESC, and a run() function that returns a string.
"""

import os
import sys

TOOL_NAME = "run_api_generator"
TOOL_DESC = """Generate REST API endpoints from a schema"""

def run(schema, output_path):
    try:
        api_code = ''
        for endpoint, endpoint_schema in schema.items():
            api_code += f'@app.route(\'{endpoint}\')\ndef {endpoint}_handler(request):\n'
            api_code += '    try:\n'
            api_code += '        # Handle request\n'
            api_code += '        return {{\'status\': \'OK\'}}, 200\n'
            api_code += '    except Exception as e:\n'
            api_code += '        return {{\'status\': \'Error\'}}, 500\n'
            api_code += '\n'
        with open(output_path, 'w') as f:
            f.write(api_code)
        return api_code
    except Exception as e:
        return f'[TOOL ERROR] Failed to generate API code: {e}'

def json_to_str(schema):
    return json.dumps(schema, indent=4)

import json


# ── CLI entry point (tools/run convention) ───────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        print(run(*args))
    except Exception as exc:
        print(f"[TOOL ERROR] {{exc}}")
        sys.exit(1)

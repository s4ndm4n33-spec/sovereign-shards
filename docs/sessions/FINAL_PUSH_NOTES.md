# Final Push Notes (2026-05-04)

## Goals
- Keep the chat loop natural-language first.
- Ensure local tool use remains optional and structured.
- Provide an operator-grade user manual for setup, operation, and troubleshooting.

## Changes Made
1. Improved CLI discoverability with a `--manual` flag that prints the user manual path.
2. Added `/help` and `/tools` commands in interactive chat mode so users can quickly learn controls without leaving the loop.
3. Added a bounded multi-tool execution loop (up to 3 tool hops) so tool-augmented replies complete in one turn while avoiding infinite loops.
4. Added explicit local server log path at startup for easier debugging.
5. Added a complete user manual (`docs/USER_MANUAL.md`) covering install, operation, commands, architecture, troubleshooting, and best practices.

## Validation
- Static check: `python -m compileall run.py app`


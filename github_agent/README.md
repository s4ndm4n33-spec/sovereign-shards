# J GitHub Agent

This package provides a GitHub Actions-based agent for `Sovereign Shards`.
It responds to `/j` issue/PR comments and performs auto-review tasks using the GitHub Models API.

## Setup

1. Ensure `httpx` is listed in `requirements.txt`.
2. GitHub Actions will provide `GITHUB_TOKEN` automatically.
3. The workflow uses these environment variables:
   - `J_LLM_BACKEND=github_models`
   - `J_MODEL=gpt-4o-mini`
   - `J_TOOL_BUDGET=3`

## Usage

The workflow triggers on:

- `issue_comment` when the comment body starts with `/j`
- `pull_request` opened or synchronized

Supported commands in issue comments:

- `/j review` — review PR changes
- `/j explain <file>` — explain a module
- `/j test <file>` — suggest test cases
- `/j plan <feature>` — break down into tasks

For pull requests, the agent performs an automatic review on open and synchronize events.

## Output

The agent writes its final response to `j_response.md` in the repository root.
That file is ignored by Git.

## Implementation

- `github_agent/run.py` — main workflow runner
- `github_agent/llm_github.py` — GitHub Models API adapter
- `github_agent/__init__.py` — package marker

## Notes

`github_agent/run.py` imports the local `app` package and uses `app.action.extract_action` and `app.agent.ToolRegistry` to support tool-driven reasoning.

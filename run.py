"""Start the Sovereign Shard chat loop."""

from __future__ import annotations

import argparse
from pathlib import Path
from app.chat import run_chat

sandbox_enabled = False

BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    """Run the shard in interactive or one-shot mode."""

    parser = argparse.ArgumentParser(description="Run the Sovereign Shard.")
    parser.add_argument("--message", help="Send a single prompt and exit.")
    parser.add_argument("--paths", action="store_true")
    parser.add_argument("--manual", action="store_true", help="Print the user manual path.")

    args = parser.parse_args()

    if args.manual:
        print(BASE_DIR / "docs" / "USER_MANUAL.md")
        return

    if args.paths:
        print(f"Shard: {BASE_DIR}")
        print(f"Python: {BASE_DIR / 'python.exe'}")
        print(f"Server: {BASE_DIR / 'model-server' / 'server.exe'}")
        print(f"CLI: {BASE_DIR / 'model-server' / 'llama.exe'}")
        print(f"Model: {BASE_DIR / 'models' / 'J.gguf'}")
        return

    runtime_state = {
        "sandbox_enabled": False
    }

    run_chat(
        initial_message=args.message,
        runtime_state=runtime_state
    )


if __name__ == "__main__":
    main()

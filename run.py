# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Start the Sovereign Shard chat loop."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.chat import run_chat
from app.client import create_client
from app.doctor import run_doctor


BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    """Run the shard in interactive, one-shot, or diagnostic mode."""
    parser = argparse.ArgumentParser(description="Run the Sovereign Shard.")
    parser.add_argument("--message", help="Send a single prompt and exit.")
    parser.add_argument(
        "--paths", action="store_true",
        help="Print the shard-local runtime paths and exit.",
    )
    parser.add_argument(
        "--doctor", action="store_true",
        help="Run startup preflight diagnostics and exit.",
    )
    parser.add_argument(
        "--manual", action="store_true",
        help="Print the user manual path and exit.",
    )
    parser.add_argument(
        "--mode", choices=["manual", "semi", "auto-safe", "auto-full"],
        default="semi",
        help="Autonomy level (default: semi).",
    )
    args = parser.parse_args()

    if args.paths:
        config = create_client()
        print(f"Shard:   {BASE_DIR}")
        print(f"Server:  {config.server_binary}")
        print(f"CLI:     {config.cli_binary}")
        print(f"Model:   {config.model_path}")
        return

    if args.doctor:
        raise SystemExit(run_doctor())

    if args.manual:
        manual = BASE_DIR / "docs" / "USER_MANUAL.md"
        print(f"Manual: {manual}")
        return

    run_chat(initial_message=args.message, autonomy_mode=args.mode)


if __name__ == "__main__":
    main()

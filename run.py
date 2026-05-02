"""Sovereign Shard Deployment Entry Point

Single command to launch the full agent with diagnostics.
"""
import os 
import sys
import argparse
from app.doctor import run_doctor
from app.local_server import LocalLlamaServer
from app.client import create_client

os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
def main():
    parser = argparse.ArgumentParser(
        description="B.L.U.E.-J. Sovereign Shard Runtime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  python run.py                # Launch interactive chat
  python run.py --doctor       # Run diagnostics
  python run.py --no-llm       # Launch without LLM (tool-only mode)
  python run.py --verbose      # Enable debug output
        """,
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run preflight diagnostics and exit",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM (tool-only mode)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args, unknown = parser.parse_known_args()

    if args.doctor:
        sys.exit(run_doctor())

    # Launch chat
    try:
        # Try to start LLM server if configured
        try:
            config = create_client()
            if not args.no_llm:
                server = LocalLlamaServer(config)
                server.ensure_started()
        except Exception as e:
            if args.verbose:
                print(f"[WARN] LLM startup: {e}")

        # Start chat loop
        from app.chat import run_chat
        run_chat()

    except ImportError as e:
        print(f"[FATAL]: Import error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[SYSTEM]: Manual shutdown initiated.")
        sys.exit(0)
    except Exception as e:
        print(f"[FATAL]: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

import sys
import argparse
from app.doctor import run_doctor

def main():
    parser = argparse.ArgumentParser(description="Sovereign Shard Runtime")
    parser.add_argument("--doctor", action="store_true", help="Run preflight diagnostics")
    args, unknown = parser.parse_known_args()

    if args.doctor:
        sys.exit(run_doctor())

    # This is the critical transition from "Placeholder" to "Active Loop"
    try:
        from app.chat import run_chat
        run_chat()
    except ImportError as e:
        print(f"[FATAL]: Could not find run_chat in app.chat. {e}")
    except KeyboardInterrupt:
        print("\n[SYSTEM]: Manual shutdown initiated.")

if __name__ == "__main__":
    main()
import argparse
import time

def manage_session(name, chars=None):
    if chars:
        print(f"[SESSION: {name}] Feeding input: {chars}")
        time.sleep(0.25) 
        return f"Input '{chars}' sent to {name}."
    return f"New interactive session '{name}' initialized."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session_name", required=True)
    parser.add_argument("--chars", default=None)
    args = parser.parse_args()
    print(manage_session(args.session_name, args.chars))

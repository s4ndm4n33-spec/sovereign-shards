import json
import argparse
import os

def request_secrets(keys, message):
    print(f"\n[SECURE REQUEST]: {message}")
    secrets = {}
    for key in keys:
        value = input(f"Enter value for {key}: ")
        secrets[key] = value
        # In a local Shard, we simulate adding to environment
        os.environ[key] = value
    
    # Save to a local .env for persistence on the Kingston drive
    with open(".env", "a") as f:
        for k, v in secrets.items():
            f.write(f"{k}={v}\n")
    return f"Successfully updated {len(keys)} secrets."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret_keys", nargs='+', required=True)
    parser.add_argument("--user_message", required=True)
    args = parser.parse_args()
    print(request_secrets(args.secret_keys, args.user_message))

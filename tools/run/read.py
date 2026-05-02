import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--path", required=True)
args = parser.parse_args()

target = Path(args.path)
if target.exists():
    with open(target, "r", encoding="utf-8") as f:
        print(f.read(), end="")
else:
    print(f"[READ ERROR] Not found: {target}")

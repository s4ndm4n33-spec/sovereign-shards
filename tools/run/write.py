import argparse
import os
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--path", required=True)
parser.add_argument("--content", required=True)
args = parser.parse_args()

target = Path(args.path)
target.parent.mkdir(parents=True, exist_ok=True)

# ATOMIC WRITE STRATEGY: Write to temp, then rename.
# This prevents file corruption if the Kingston 2.0 is unplugged.
temp_file = target.with_suffix('.tmp')
try:
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(args.content)
        f.flush()
        os.fsync(f.fileno()) # Force physical commit to NAND
    
    # Atomic replace
    os.replace(temp_file, target)
    print(f"[WRITE OK] {target}")
except Exception as e:
    if temp_file.exists():
        os.remove(temp_file)
    print(f"[WRITE ERROR] {e}")

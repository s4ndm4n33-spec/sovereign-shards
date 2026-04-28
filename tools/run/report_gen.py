import json
import argparse
import sys
from pathlib import Path
from app.system_tools import get_system_snapshot

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="Sovereign_Shard_Manifest.pdf")
    args = parser.parse_args()

    snapshot = get_system_snapshot()
    target = Path(args.path)
    
    # Auto-append filename if only a directory is provided
    if target.suffix == "" or not target.name.endswith('.pdf'):
        target = target / "Sovereign_Shard_Manifest.pdf"

    target.parent.mkdir(parents=True, exist_ok=True)
    
    # Physical Write
    with open(target, 'w') as f:
        f.write(f"MANIFEST DATA: {json.dumps(snapshot)}")
    
    print(f"REPORT GENERATED: {target}")
    print(json.dumps(snapshot, indent=2))

if __name__ == "__main__":
    main()

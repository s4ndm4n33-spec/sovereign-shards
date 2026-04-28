import os
import hashlib
from pathlib import Path

def get_hash(file_path):
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        return f"ERROR: {str(e)}"

def run_integrity_check():
    print("--- HAMILTON DYNAMIC SWEEP START ---")
    # Resolve the root and the tools/run directory
    current_dir = Path(__file__).resolve().parent
    root = current_dir.parent.parent
    tools_dir = current_dir # We are inside tools/run/
    
    # Files to track
    found_errors = 0
    
    # 1. Check Core Logic
    core_files = [root / "app/chat.py", root / "app/agent/executor.py", root / "app/agent/planner.py"]
    print("\n[SECTION: CORE LOGIC]")
    for target in core_files:
        if target.exists():
            print(f"[OK] CORE: {target.name} ({get_hash(target)[:12]})")
        else:
            print(f"[!!] MISSING CORE: {target}")
            found_errors += 1

    # 2. Check Dynamic Tools Folder
    print("\n[SECTION: TOOLS/RUN]")
    for tool_file in tools_dir.glob("*.py"):
        print(f"[OK] TOOL: {tool_file.name} ({get_hash(tool_file)[:12]})")
            
    print(f"\n--- SWEEP COMPLETE: {found_errors} CORE ERRORS FOUND ---")

if __name__ == "__main__":
    run_integrity_check()
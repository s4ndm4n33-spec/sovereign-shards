import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--query", required=True)
parser.add_argument("--root", default=".")
args = parser.parse_args()

search_root = Path(args.root).resolve()
ignore_dirs = {'.git', '__pycache__', '.venv', 'node_modules'}
ignore_exts = {'.pyc', '.pyo', '.pyd', '.exe', '.bin'}

found = []

for root, dirs, files in os.walk(search_root):
    # Prune ignored directories in-place
    dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
    
    for name in files:
        file_path = Path(root) / name
        if file_path.suffix.lower() in ignore_exts:
            continue
            
        try:
            # Match in filename (case-insensitive)
            if args.query.lower() in name.lower():
                found.append(str(file_path.relative_to(search_root)))
                continue
                
            # Match in content (limit to text-ish files under 500KB)
            if file_path.stat().st_size < 500000:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    if args.query.lower() in f.read().lower():
                        found.append(str(file_path.relative_to(search_root)))
        except:
            continue

# Output clean relative paths
for path in found[:15]:
    print(path.replace('\\', '/'))

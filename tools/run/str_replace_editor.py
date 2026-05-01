import sys
import argparse
import os

def cat_n(path, view_range=None):
    if not os.path.exists(path):
        return f"Error: {path} not found."
    with open(path, 'r') as f:
        lines = f.readlines()
    
    start, end = (1, len(lines)) if not view_range else view_range
    output = ""
    for i, line in enumerate(lines[start-1:end], start=start):
        output += f"{i:6}\t{line}"
    return output

def str_replace(path, old_str, new_str):
    if not os.path.exists(path):
        return f"Error: {path} not found."
    with open(path, 'r') as f:
        content = f.read()
    
    if content.count(old_str) != 1:
        return "Error: old_str must be unique in the file."
    
    new_content = content.replace(old_str, new_str)
    with open(path, 'w') as f:
        f.write(new_content)
    return f"Successfully updated {path}."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", choices=['view', 'str_replace'], required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--old_str", default="")
    parser.add_argument("--new_str", default="")
    args = parser.parse_args()

    if args.command == 'view':
        print(cat_n(args.path))
    elif args.command == 'str_replace':
        print(str_replace(args.path, args.old_str, args.new_str))

import os
import argparse

def search_files(query):
    results = []
    root_dir = "." 
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith((".py", ".md", ".txt")):
                path = os.path.join(root, file)
                with open(path, 'r', errors='ignore') as f:
                    if query.lower() in f.read().lower():
                        results.append(path)
    return "\n".join(results) if results else "No matches found."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query_description", required=True)
    args = parser.parse_args()
    print(f"SEARCH RESULTS for '{args.query_description}':\n{search_files(args.query_description)}")

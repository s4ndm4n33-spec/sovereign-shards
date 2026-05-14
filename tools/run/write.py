import sys


path = sys.argv[1]
if len(sys.argv) > 2:
    data = sys.argv[2]
else:
    data = sys.stdin.read()

with open(path, "w", encoding="utf-8") as handle:
    handle.write(data)

print(f"[WRITE OK] {path}")

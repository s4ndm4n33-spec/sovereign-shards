import argparse

def report(summary):
    # Fulfills requirement to use simple language and icons
    items = summary.split('|')
    print("\n--- PROGRESS REPORT ---")
    for item in items[:5]:
        print(f"{item.strip()}")
    print("\n[SYSTEM]: Progress logged. Awaiting next directive, Sir.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()
    report(args.summary)

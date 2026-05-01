import argparse
from app.bible_logic import BibleInterface

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--master', required=True)
    parser.add_argument('--verse', required=True)
    args = parser.parse_args()

    bible = BibleInterface()
    result = bible.add_verse(args.master, args.verse)
    if result is True:
        print(f'[CODIFIED] Verse saved to Kingston Shard.')
    else:
        print(result)

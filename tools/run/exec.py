import argparse
import subprocess
import sys

def main():
    # The 'nargs=argparse.REMAINDER' tells Python: 
    # 'Everything after this flag belongs to this flag.'
    parser = argparse.ArgumentParser()
    parser.add_argument('--command', nargs=argparse.REMAINDER, required=True)
    args = parser.parse_args()
    
    # Rejoin the list of words into a single string
    full_command = ' '.join(args.command)
    
    try:
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    main()
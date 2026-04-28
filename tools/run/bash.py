import sys
import subprocess
import argparse

def execute_bash(command):
    try:
        # Fulfills requirement to handle long-lived commands or simple execution
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        if stderr:
            return f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        return stdout if stdout else "Command executed successfully with no output."
    except Exception as e:
        return f"Execution Error: {str(e)}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    print(execute_bash(args.command))

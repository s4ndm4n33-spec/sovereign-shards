import subprocess
import argparse

def manage_packages(libs, action):
    cmd = f"pip {action} {' '.join(libs)} -y" if action == "uninstall" else f"pip install {' '.join(libs)}"
    try:
        subprocess.run(cmd, shell=True, check=True)
        return f"Successfully {action}ed: {', '.join(libs)}"
    except Exception as e:
        return f"Package Error: {str(e)}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--libs", nargs='+', required=True)
    parser.add_argument("--action", choices=['install', 'uninstall'], default='install')
    args = parser.parse_args()
    print(manage_packages(args.libs, args.action))

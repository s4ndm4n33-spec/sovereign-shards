#!/usr/bin/env python3
# Copyright (c) 2026 Mike McCollum
#
# Licensed under the Sovereign Shards License.
# See LICENSE.md for details.

"""
Sovereign IDE v2 - VS Code Clone
Quick launch script with auto-browser opening
"""
import subprocess
import time
import webbrowser
import os
import sys

def launch_ide():
    print("""
╔════════════════════════════════════════════════════════════════╗
║             SOVEREIGN IDE v2 — VS Code Clone                   ║
║                                                                ║
║  Exact architecture replica with file explorer, editor tabs,  ║
║  git integration, and command palette foundation              ║
╚════════════════════════════════════════════════════════════════╝
    """)

    # Start server
    print("[*] Starting Sovereign IDE server...")
    print("[*] To stop: Press Ctrl+C\n")

    # Auto-open browser after delay
    def open_browser():
        time.sleep(2)
        url = "http://localhost:8000"
        print(f"[+] Opening browser: {url}")
        webbrowser.open(url)

    import threading
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Run server
    os.system("python server.py")

if __name__ == "__main__":
    try:
        launch_ide()
    except KeyboardInterrupt:
        print("\n\n[!] IDE shutdown.")
        sys.exit(0)

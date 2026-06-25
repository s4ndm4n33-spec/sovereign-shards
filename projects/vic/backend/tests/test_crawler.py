"""Crawler smoke test: serve a fake share page, hit /api/crawl, verify result."""

import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vic.app import app  # noqa: E402

# Fake ChatGPT share page with __NEXT_DATA__ blob containing a real mapping.
CHATGPT_HTML = """<!doctype html>
<html><head><title>ChatGPT share — VIC arch</title></head>
<body>
<div data-message-author-role="user">We decided to use Flask for the backend of VIC.</div>
<div data-message-author-role="assistant">Good choice. I'd avoid anything heavier.</div>
<div data-message-author-role="user">There's a bug in the parser — should we refactor?</div>
<div data-message-author-role="assistant">Fixed it by validating types. The architecture now separates detect and parse layers.</div>
</body></html>
"""

# Fake Claude share page using font-user/font-claude markers.
CLAUDE_HTML = """<!doctype html>
<html><head><title>Claude share — memory refactor</title></head>
<body>
<div class="font-user">We decided to migrate the memory module to a class.</div>
<div class="font-claude">Resolved the retention bug by adding a guard.</div>
<div class="font-user">Should we keep backwards-compatible shims?</div>
<div class="font-claude">Let's stick with the modular architecture we chose earlier.</div>
</body></html>
"""


def main() -> int:
    # Start a tiny HTTP server on a free port serving both pages
    pages = {"/chatgpt": CHATGPT_HTML, "/claude": CLAUDE_HTML}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = pages.get(self.path, "not found").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # silence
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            client = app.test_client()
            # ChatGPT share URL
            url1 = f"http://127.0.0.1:{port}/chatgpt"
            r = client.post("/api/crawl", json={"url": url1})
            assert r.status_code == 200, f"chatgpt crawl failed: {r.status_code} {r.data[:300]}"
            body = r.get_json()
            assert body["providers"] == ["chatgpt"], body["providers"]
            assert body["session_count"] >= 1
            assert body["jsonl"], "no jsonl"
            # Claude share URL
            url2 = f"http://127.0.0.1:{port}/claude"
            r = client.post("/api/crawl", json={"url": url2})
            assert r.status_code == 200, f"claude crawl failed: {r.status_code} {r.data[:300]}"
            body = r.get_json()
            assert body["providers"] == ["claude"], body["providers"]
            assert body["session_count"] >= 1
            # Multi-URL crawl
            r = client.post("/api/crawl", json={"urls": [url1, url2]})
            assert r.status_code == 200, f"multi-crawl failed: {r.status_code}"
            body = r.get_json()
            assert set(body["providers"]) == {"chatgpt", "claude"}, body["providers"]
            assert body["session_count"] == 2

            print(f"PASS — crawled chatgpt + claude share pages")
            print(f"  providers={body['providers']} sessions={body['session_count']}")
            print(f"  themes={body['themes'][:3]}")
            return 0
        finally:
            httpd.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())

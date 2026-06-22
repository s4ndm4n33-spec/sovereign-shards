"""V.I.C. Flask backend.

Endpoints:
  POST /api/process   — accept multipart upload (ZIPs + JSON files), process, return preview
  POST /api/pdf        — accept JSON body, return rendered PDF
  POST /api/jsonl      — accept JSON body, return archive.jsonl
  GET  /api/health     — liveness check

No persistence: all work happens in temp dirs that are deleted per request.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file, abort

from .pipeline import ProcessResult, make_pdf_bytes, process_inputs, result_to_dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("vic.app")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512MB ceiling

    @app.after_request
    def _no_store(resp):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        # CORS-free (local sovereign) but allow localhost dev origins
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Client-Info"
        return resp

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "name": "V.I.C."})

    @app.route("/api/process", methods=["POST"])
    def process():
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "No files uploaded"}), 400

        zip_paths: list[Path] = []
        json_paths: list[Path] = []
        tmpdir = tempfile.mkdtemp(prefix="vic-")
        try:
            for f in files:
                name = os.path.basename(f.filename or "")
                if not name:
                    continue
                dest = Path(tmpdir) / name
                f.save(dest)
                lower = name.lower()
                if lower.endswith(".zip"):
                    zip_paths.append(dest)
                elif lower.endswith(".json"):
                    json_paths.append(dest)
                elif lower.endswith(".jsonl"):
                    json_paths.append(dest)
                else:
                    # Unknown extension — try as JSON
                    json_paths.append(dest)

            log.info("Processing %d ZIP(s) and %d JSON file(s)", len(zip_paths), len(json_paths))
            result = process_inputs(zip_paths, json_paths)
            return jsonify(result_to_dict(result))
        except Exception as exc:  # noqa: BLE001
            log.exception("Processing failed")
            return jsonify({"error": str(exc)}), 500
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    @app.route("/api/pdf", methods=["POST"])
    def pdf():
        payload = request.get_json(silent=True) or {}
        title = payload.get("title") or "AI Chat Archive"
        sessions = payload.get("sessions")
        providers = payload.get("providers", [])
        exec_summary = payload.get("exec_summary", "")
        result = _reconstruct_result(sessions, providers, exec_summary, payload.get("themes", []))
        try:
            pdf_bytes = make_pdf_bytes(result, title)
        except Exception as exc:  # noqa: BLE001
            log.exception("PDF generation failed")
            return jsonify({"error": str(exc)}), 500
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="VIC-report.pdf",
        )

    @app.route("/api/jsonl", methods=["POST"])
    def jsonl():
        payload = request.get_json(silent=True) or {}
        jsonl_text = payload.get("jsonl") or ""
        if not jsonl_text:
            return jsonify({"error": "Missing jsonl payload"}), 400
        return send_file(
            io.BytesIO(jsonl_text.encode("utf-8")),
            mimetype="application/x-jsonlines",
            as_attachment=True,
            download_name="archive.jsonl",
        )

    return app


def _reconstruct_result(sessions, providers, exec_summary, themes) -> ProcessResult:
    from .pipeline import ProcessResult

    if sessions is None:
        sessions = []
    if not providers and sessions:
        providers = sorted({s.get("provider", "unknown") for s in sessions})
    session_count = len(sessions)
    message_count = sum(int(s.get("message_count", 0)) for s in sessions)
    dates = [s.get("date") for s in sessions if s.get("date") and s.get("date") != "unknown"]
    date_range = (min(dates), max(dates)) if dates else ("unknown", "unknown")
    # jsonl isn't needed for PDF
    return ProcessResult(
        providers=providers,
        session_count=session_count,
        message_count=message_count,
        date_range=tuple(date_range),
        themes=[(t, n) if isinstance(t, str) else (str(t), 0) for t, n in (themes or [])],
        projects={},
        sessions=sessions,
        jsonl="",
        exec_summary=exec_summary,
    )


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8001, debug=False)

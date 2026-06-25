"""V.I.C. Flask backend.

Endpoints:
  POST /api/process        — accept multipart upload (ZIPs + JSON files), process, return preview
  POST /api/crawl          — crawl shared chat URL(s), process, return preview
  POST /api/pdf            — accept JSON body, return rendered PDF
  POST /api/jsonl          — accept JSON body, return archive.jsonl
  GET  /api/health          — liveness check

  Historian endpoints (automated software historian):
  POST /api/ingest/git       — ingest a local git repo by path
  POST /api/ingest/markdown — ingest a markdown document
  POST /api/ingest/notes    — ingest structured notes (JSON)
  POST /api/ingest/github   — ingest a GitHub PR/issue export (JSON)
  GET  /api/timeline         — chronological timeline with links
  GET  /api/events           — list events (filtered)
  GET  /api/decisions        — list decisions
  GET  /api/artifacts        — list artifacts
  GET  /api/milestones       — list milestones
  GET  /api/persons          — list persons
  GET  /api/repositories     — list repositories
  GET  /api/stats            — store statistics
  GET  /api/search           — semantic search (TF-IDF + FTS5)
  POST /api/ask              — answer a historical question
  POST /api/narrative        — generate a narrative report
  GET  /api/narratives       — list generated narratives

Sovereignty: chat-archive processing is stateless (temp dirs deleted per
request). The historian store uses a local embedded SQLite file on the
user's machine — never a cloud database.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file, abort

from .crawler import CrawlError, crawl_chat_url, detect_provider_from_url
from .pipeline import ProcessResult, make_pdf_bytes, process_conversations, process_inputs, result_to_dict
from .store import Store
from .ingest import ingest_git, ingest_markdown, ingest_structured_notes, ingest_github_export, ingest_conversations
from .timeline import build_timeline, answer_question
from .narrator import (
    generate_executive_summary,
    generate_architectural_evolution,
    generate_dependency_evolution,
    generate_state_of_project,
    generate_decision_tree,
    generate_from_query,
)
from .models import Conversation, Message

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

    @app.route("/api/crawl", methods=["POST"])
    def crawl():
        payload = request.get_json(silent=True) or {}
        url = (payload.get("url") or "").strip()
        urls = payload.get("urls") or []
        if not url and not urls:
            return jsonify({"error": "No URL provided"}), 400
        all_urls = [url] + [u for u in urls if u]
        all_urls = [u.strip() for u in all_urls if u.strip()]
        valid_schemes = ("http://", "https://")
        bad = [u for u in all_urls if not u.lower().startswith(valid_schemes)]
        if bad:
            return jsonify({"error": "Only http(s) URLs are supported", "rejected": bad}), 400
        try:
            conversations = []
            errors: list[dict] = []
            for u in all_urls:
                try:
                    conversations.append(crawl_chat_url(u))
                except CrawlError as ce:
                    errors.append({"url": u, "error": ce.reason})
                except Exception as exc:  # noqa: BLE001
                    errors.append({"url": u, "error": str(exc)})
            if not conversations:
                return jsonify({"error": "No conversations could be crawled", "details": errors}), 422
            result = process_conversations(conversations)
            out = result_to_dict(result)
            if errors:
                out["crawl_warnings"] = errors
            return jsonify(out)
        except Exception as exc:  # noqa: BLE001
            log.exception("Crawl processing failed")
            return jsonify({"error": str(exc)}), 500

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

    # ===================================================================
    # Historian endpoints
    # ===================================================================

    def _store() -> Store:
        if not hasattr(app, "_vic_store"):
            app._vic_store = Store()
        return app._vic_store

    @app.route("/api/stats")
    def stats():
        return jsonify(_store().stats())

    @app.route("/api/repositories")
    def repositories():
        return jsonify(_store().list_repositories())

    @app.route("/api/persons")
    def persons():
        repo_id = request.args.get("repository_id")
        return jsonify(_store().list_persons(repository_id=repo_id))

    @app.route("/api/events")
    def events():
        repo_id = request.args.get("repository_id")
        kind = request.args.get("kind")
        since = request.args.get("since")
        until = request.args.get("until")
        limit = int(request.args.get("limit", 500))
        return jsonify(_store().list_events(repository_id=repo_id, kind=kind, since=since, until=until, limit=limit))

    @app.route("/api/decisions")
    def decisions():
        repo_id = request.args.get("repository_id")
        return jsonify(_store().list_decisions(repository_id=repo_id))

    @app.route("/api/artifacts")
    def artifacts():
        repo_id = request.args.get("repository_id")
        kind = request.args.get("kind")
        return jsonify(_store().list_artifacts(repository_id=repo_id, kind=kind))

    @app.route("/api/milestones")
    def milestones():
        repo_id = request.args.get("repository_id")
        return jsonify(_store().list_milestones(repository_id=repo_id))

    @app.route("/api/timeline")
    def timeline():
        repo_id = request.args.get("repository_id")
        since = request.args.get("since")
        until = request.args.get("until")
        kinds = request.args.getlist("kind")
        limit = int(request.args.get("limit", 1000))
        return jsonify(build_timeline(_store(), repository_id=repo_id, since=since, until=until, kinds=kinds or None, limit=limit))

    @app.route("/api/search")
    def search():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"error": "Missing query parameter 'q'"}), 400
        repo_id = request.args.get("repository_id")
        mode = request.args.get("mode", "semantic")
        limit = int(request.args.get("limit", 20))
        if mode == "fulltext":
            return jsonify(_store().search_fulltext(q, repository_id=repo_id, limit=limit))
        return jsonify(_store().search_semantic(q, repository_id=repo_id, limit=limit))

    @app.route("/api/ask", methods=["POST"])
    def ask():
        payload = request.get_json(silent=True) or {}
        question = (payload.get("question") or "").strip()
        if not question:
            return jsonify({"error": "Missing 'question'"}), 400
        repo_id = payload.get("repository_id")
        return jsonify(answer_question(_store(), question, repository_id=repo_id))

    @app.route("/api/narrative", methods=["POST"])
    def narrative():
        payload = request.get_json(silent=True) or {}
        kind = (payload.get("kind") or "executive_summary").strip()
        repo_id = payload.get("repository_id")
        since = payload.get("since")
        until = payload.get("until")
        at_date = payload.get("at_date")
        query = payload.get("query")
        if kind == "executive_summary":
            n = generate_executive_summary(_store(), repository_id=repo_id, since=since, until=until)
        elif kind == "arch_evolution":
            n = generate_architectural_evolution(_store(), repository_id=repo_id, since=since, until=until)
        elif kind == "dep_evolution":
            n = generate_dependency_evolution(_store(), repository_id=repo_id, since=since, until=until)
        elif kind == "state_of_project":
            n = generate_state_of_project(_store(), repository_id=repo_id, at_date=at_date or until)
        elif kind == "decision_tree":
            n = generate_decision_tree(_store(), repository_id=repo_id)
        elif kind == "custom":
            n = generate_from_query(_store(), query or "", repository_id=repo_id)
        else:
            return jsonify({"error": f"Unknown narrative kind: {kind}"}), 400
        from .historian_model import to_dict
        return jsonify(to_dict(n))

    @app.route("/api/narratives")
    def narratives():
        repo_id = request.args.get("repository_id")
        return jsonify(_store().list_narratives(repository_id=repo_id))

    @app.route("/api/ingest/git", methods=["POST"])
    def ingest_git_route():
        payload = request.get_json(silent=True) or {}
        repo_path = payload.get("path")
        if not repo_path:
            return jsonify({"error": "Missing 'path'"}), 400
        repo_id = payload.get("repository_id")
        limit = int(payload.get("limit", 5000))
        try:
            result = ingest_git(_store(), repo_path, repo_id=repo_id, limit=limit)
            _invalidate_kg()
            return jsonify(result)
        except (FileNotFoundError, OSError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/ingest/markdown", methods=["POST"])
    def ingest_markdown_route():
        payload = request.get_json(silent=True) or {}
        path = payload.get("path")
        repo_id = payload.get("repository_id")
        if not path or not repo_id:
            return jsonify({"error": "Missing 'path' or 'repository_id'"}), 400
        try:
            result = ingest_markdown(_store(), path, repo_id=repo_id)
            _invalidate_kg()
            return jsonify(result)
        except (FileNotFoundError, OSError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/ingest/notes", methods=["POST"])
    def ingest_notes_route():
        payload = request.get_json(silent=True) or {}
        path = payload.get("path")
        repo_id = payload.get("repository_id")
        if not path or not repo_id:
            return jsonify({"error": "Missing 'path' or 'repository_id'"}), 400
        try:
            result = ingest_structured_notes(_store(), path, repo_id=repo_id)
            _invalidate_kg()
            return jsonify(result)
        except (FileNotFoundError, OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/ingest/github", methods=["POST"])
    def ingest_github_route():
        payload = request.get_json(silent=True) or {}
        path = payload.get("path")
        repo_id = payload.get("repository_id")
        if not path or not repo_id:
            return jsonify({"error": "Missing 'path' or 'repository_id'"}), 400
        try:
            result = ingest_github_export(_store(), path, repo_id=repo_id)
            return jsonify(result)
        except (FileNotFoundError, OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    # ===================================================================
    # V2 — Knowledge Graph, Biography, Evolution, Provenance
    # ===================================================================

    def _kg() -> "KnowledgeGraph":
        from .knowledge_graph import KnowledgeGraph
        if not hasattr(app, "_vic_kg_cache"):
            app._vic_kg_cache = {}
        repo = request.args.get("repository_id") if request else None
        if repo not in app._vic_kg_cache:
            app._vic_kg_cache[repo] = KnowledgeGraph(_store(), repository_id=repo)
        return app._vic_kg_cache[repo]

    def _invalidate_kg() -> None:
        if hasattr(app, "_vic_kg_cache"):
            app._vic_kg_cache.clear()

    @app.route("/api/graph")
    def graph():
        repo_id = request.args.get("repository_id")
        from .knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph(_store(), repository_id=repo_id)
        node_id = request.args.get("node_id")
        if node_id:
            neighbors = kg.neighbors(node_id)
            incoming = kg.incoming(node_id)
            node = kg.nodes.get(node_id, {})
            return jsonify({"node": node, "neighbors": neighbors, "incoming": incoming, "graph_stats": kg.to_dict()})
        return jsonify(kg.to_dict())

    @app.route("/api/biography", methods=["POST"])
    def biography():
        from .biography import generate_biography
        from .knowledge_graph import KnowledgeGraph
        payload = request.get_json(silent=True) or {}
        concept = (payload.get("concept") or "").strip()
        if not concept:
            return jsonify({"error": "Missing 'concept'"}), 400
        repo_id = payload.get("repository_id")
        kg = KnowledgeGraph(_store(), repository_id=repo_id)
        return jsonify(generate_biography(kg, concept, repository_id=repo_id))

    @app.route("/api/evolution", methods=["POST"])
    def evolution():
        from .evolution import run_evolution_query
        from .knowledge_graph import KnowledgeGraph
        payload = request.get_json(silent=True) or {}
        query = (payload.get("query") or "all").strip()
        repo_id = payload.get("repository_id")
        kg = KnowledgeGraph(_store(), repository_id=repo_id)
        return jsonify(run_evolution_query(kg, query, repository_id=repo_id))

    @app.route("/api/provenance")
    def provenance():
        """Return the evidence chain for a specific event or claim."""
        event_id = request.args.get("event_id")
        if not event_id:
            return jsonify({"error": "Missing 'event_id'"}), 400
        from .knowledge_graph import KnowledgeGraph
        repo_id = request.args.get("repository_id")
        kg = KnowledgeGraph(_store(), repository_id=repo_id)
        node = kg.nodes.get(event_id)
        if not node:
            return jsonify({"error": "Event not found"}), 404
        incoming = kg.incoming(event_id)
        outgoing = kg.neighbors(event_id)
        # Build provenance chain: what evidence supports this event's relationships?
        evidence: list[dict] = []
        for n in incoming:
            evidence.append({"event_id": n["id"], "title": n.get("title", ""), "relation": n.get("_edge_type", ""), "confidence": n.get("_confidence", 0), "rationale": n.get("_rationale", ""), "occurred_at": n.get("occurred_at"), "source_kind": n.get("source_kind", "")})
        for n in outgoing:
            evidence.append({"event_id": n["id"], "title": n.get("title", ""), "relation": n.get("_edge_type", ""), "confidence": n.get("_confidence", 0), "rationale": n.get("_rationale", ""), "occurred_at": n.get("occurred_at"), "source_kind": n.get("source_kind", "")})
        return jsonify({"event": node, "evidence": evidence})

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

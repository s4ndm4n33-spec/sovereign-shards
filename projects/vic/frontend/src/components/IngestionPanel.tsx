import { useState } from "react";
import { api } from "../lib/history-api";

export function IngestionPanel({ repositoryId, onIngested }: { repositoryId?: string; onIngested?: () => void }) {
  const [path, setPath] = useState("");
  const [repoId, setRepoId] = useState(repositoryId || "default");
  const [loading, setLoading] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ingest(type: "git" | "markdown" | "notes") {
    if (!path.trim()) return;
    setLoading(type);
    setError(null);
    setResult(null);
    try {
      let r: Record<string, unknown>;
      if (type === "git") r = await api.ingestGit(path, repoId || undefined);
      else if (type === "markdown") r = await api.ingestMarkdown(path, repoId);
      else r = await api.ingestNotes(path, repoId);
      setResult(r);
      onIngested?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingestion failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="rounded-2xl border border-ink-700/60 bg-ink-800/30 p-4">
      <h3 className="mb-3 text-sm font-semibold text-ink-100">Ingest Sources</h3>

      <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="text-[11px] uppercase tracking-wider text-ink-500">Repository ID</span>
          <input
            value={repoId}
            onChange={(e) => setRepoId(e.target.value)}
            placeholder="my-project"
            className="w-full rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-2 text-xs text-ink-100 outline-none focus:border-vic-glow/50"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[11px] uppercase tracking-wider text-ink-500">Local file / repo path</span>
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="/path/to/repo or /path/to/file.md"
            className="w-full rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-2 text-xs text-ink-100 outline-none focus:border-vic-glow/50"
          />
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <IngestButton label="Git repo" loading={loading === "git"} disabled={!path.trim()} onClick={() => ingest("git")} />
        <IngestButton label="Markdown" loading={loading === "markdown"} disabled={!path.trim()} onClick={() => ingest("markdown")} />
        <IngestButton label="Notes (JSON)" loading={loading === "notes"} disabled={!path.trim()} onClick={() => ingest("notes")} />
      </div>

      {result && (
        <div className="fade-in mt-3 rounded-lg border border-emerald-400/30 bg-emerald-500/10 p-2 text-xs text-emerald-200">
          <pre className="whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
      {error && (
        <div className="fade-in mt-3 rounded-lg border border-vic-err/40 bg-vic-err/10 p-2 text-xs text-vic-err">
          {error}
        </div>
      )}

      <p className="mt-3 text-[10px] text-ink-500">
        Paths must be accessible to the backend process. Git ingestion runs <code className="text-ink-300">git log</code> locally.
      </p>
    </div>
  );
}

function IngestButton({ label, onClick, loading, disabled }: { label: string; onClick: () => void; loading: boolean; disabled: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="rounded-lg border border-ink-600 bg-ink-700/40 px-3 py-2 text-xs font-medium text-ink-100 transition hover:border-vic-glow/40 hover:bg-ink-700/60 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {loading ? "Ingesting…" : `+ ${label}`}
    </button>
  );
}

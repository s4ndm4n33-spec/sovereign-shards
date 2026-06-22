import { useMemo, useState } from "react";
import type { ProcessResult } from "../lib/types";
import { downloadJsonl, downloadPdf } from "../lib/api";
import { ProviderBadges } from "./ProviderBadge";
import { SessionCard } from "./SessionCard";

interface ResultsPanelProps {
  result: ProcessResult;
  onReset: () => void;
}

export function ResultsPanel({ result, onReset }: ResultsPanelProps) {
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState("AI Chat Archive");
  const [downloading, setDownloading] = useState<"pdf" | "jsonl" | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return result.sessions;
    return result.sessions.filter((s) =>
      [s.title, s.summary, s.provider, s.date, ...s.decisions, ...s.bugs, ...s.fixes, ...s.open_questions]
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [result.sessions, query]);

  const [start, end] = result.date_range;

  async function handlePdf() {
    setErr(null);
    setDownloading("pdf");
    try {
      await downloadPdf(result, title || "AI Chat Archive");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "PDF generation failed");
    } finally {
      setDownloading(null);
    }
  }

  async function handleJsonl() {
    setErr(null);
    setDownloading("jsonl");
    try {
      await downloadJsonl(result);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "JSONL download failed");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="fade-in space-y-6">
      {/* Summary header */}
      <section className="rounded-2xl border border-ink-700/60 bg-ink-800/30 p-6 backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-semibold text-ink-100">Archive Processed</h2>
              <ProviderBadges providers={result.providers} />
            </div>
            <p className="mt-2 text-sm leading-relaxed text-ink-300">{result.exec_summary}</p>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-ink-300">
              <Stat label="Sessions" value={result.session_count} />
              <Stat label="Messages" value={result.message_count} />
              <Stat label="Date range" value={`${start} → ${end}`} />
              <Stat label="Projects detected" value={Object.keys(result.projects).length} />
            </div>
          </div>
          <button
            onClick={onReset}
            className="rounded-lg border border-ink-600 bg-ink-700/40 px-3 py-1.5 text-xs font-medium text-ink-100 transition hover:border-vic-glow/40 hover:bg-ink-700/60"
          >
            New archive
          </button>
        </div>

        {result.themes.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {result.themes.map(([t, n]) => (
              <span
                key={t}
                className="inline-flex items-center gap-1 rounded-md bg-ink-700/50 px-2 py-0.5 text-[11px] text-ink-100"
              >
                <span className="text-vic-glow">{t}</span>
                <span className="font-mono text-ink-500">×{n}</span>
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Export bar */}
      <section className="flex flex-wrap items-center gap-3 rounded-xl border border-ink-700/60 bg-ink-800/30 p-4">
        <label className="flex flex-1 flex-col gap-1">
          <span className="text-[11px] uppercase tracking-wider text-ink-500">Project title (for PDF)</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-2 text-sm text-ink-100 outline-none focus:border-vic-glow/50"
            placeholder="AI Chat Archive"
          />
        </label>
        <button
          onClick={handlePdf}
          disabled={downloading !== null}
          className="flex items-center gap-2 rounded-lg bg-vic-glow px-4 py-2.5 text-sm font-semibold text-ink-950 shadow-glow transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {downloading === "pdf" ? "Generating…" : (
            <>
              <DownloadIcon /> Download PDF
            </>
          )}
        </button>
        <button
          onClick={handleJsonl}
          disabled={downloading !== null}
          className="flex items-center gap-2 rounded-lg border border-vic-glow/40 bg-vic-glow/5 px-4 py-2.5 text-sm font-semibold text-vic-glow transition hover:bg-vic-glow/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {downloading === "jsonl" ? "Preparing…" : (
            <>
              <DownloadIcon /> Download JSONL
            </>
          )}
        </button>
      </section>

      {err && (
        <div className="rounded-lg border border-vic-err/40 bg-vic-err/10 p-3 text-sm text-vic-err">
          {err}
        </div>
      )}

      {/* Search */}
      <div className="flex items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search sessions, decisions, bugs…"
          className="w-full rounded-lg border border-ink-700 bg-ink-900/60 px-4 py-2.5 text-sm text-ink-100 outline-none placeholder:text-ink-500 focus:border-vic-glow/40"
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            className="rounded-lg border border-ink-700 px-3 py-2 text-xs text-ink-300 hover:bg-ink-800"
          >
            Clear
          </button>
        )}
      </div>

      {/* Session grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {filtered.map((s) => (
          <SessionCard key={s.session} session={s} />
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full rounded-lg border border-dashed border-ink-700 p-8 text-center text-sm text-ink-500">
            No sessions match "{query}". Try clearing filters.
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-ink-500">{label}</span>
      <span className="font-mono text-sm text-ink-100">{value}</span>
    </div>
  );
}

function DownloadIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className="h-4 w-4"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16" />
    </svg>
  );
}

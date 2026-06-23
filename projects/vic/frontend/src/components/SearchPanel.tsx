import { useState } from "react";
import { api, type AnswerResult, type TimelineEvent } from "../lib/history-api";

const SUGGESTED = [
  "Who introduced the registry pattern?",
  "When did we first discuss JGPU?",
  "Why did the runtime architecture change between March and June?",
  "Show me what happened between 2026-03-01 and 2026-06-01",
];

export function SearchPanel({ repositoryId }: { repositoryId?: string }) {
  const [tab, setTab] = useState<"search" | "ask">("ask");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<TimelineEvent[]>([]);
  const [answer, setAnswer] = useState<AnswerResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function doSearch() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.search(query, repositoryId, "semantic");
      setResults(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function doAsk() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.ask(query, repositoryId);
      setAnswer(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-ink-700/60 bg-ink-800/30 p-4">
      <div className="mb-3 flex items-center gap-2">
        <button
          onClick={() => setTab("ask")}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium ${tab === "ask" ? "bg-vic-glow/15 text-vic-glow" : "text-ink-300 hover:bg-ink-700/40"}`}
        >
          Ask
        </button>
        <button
          onClick={() => setTab("search")}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium ${tab === "search" ? "bg-vic-glow/15 text-vic-glow" : "text-ink-300 hover:bg-ink-700/40"}`}
        >
          Semantic Search
        </button>
      </div>

      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && tab === "search" && doSearch()}
          placeholder={tab === "ask" ? "Ask a historical question…" : "Search accumulated history…"}
          className="flex-1 rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-2 text-sm text-ink-100 outline-none placeholder:text-ink-500 focus:border-vic-glow/50"
        />
        <button
          onClick={tab === "ask" ? doAsk : doSearch}
          disabled={loading || !query.trim()}
          className="rounded-lg bg-vic-glow px-4 py-2 text-xs font-semibold text-ink-950 shadow-glow transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "…" : tab === "ask" ? "Ask" : "Search"}
        </button>
      </div>

      {tab === "ask" && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {SUGGESTED.map((s) => (
            <button
              key={s}
              onClick={() => setQuery(s)}
              className="rounded-md bg-ink-700/40 px-2 py-0.5 text-[10px] text-ink-300 transition hover:bg-ink-700/60"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {error && <div className="mt-3 rounded-lg border border-vic-err/30 bg-vic-err/10 p-2 text-xs text-vic-err">{error}</div>}

      {tab === "ask" && answer && (
        <div className="fade-in mt-3 space-y-3">
          <div className="rounded-lg border border-vic-glow/20 bg-vic-glow/5 p-3">
            <p className="whitespace-pre-wrap text-sm text-ink-100">{answer.answer}</p>
          </div>
          {answer.events?.length > 0 && (
            <div className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-ink-500">Supporting events</span>
              {answer.events.slice(0, 6).map((e) => (
                <ResultRow key={e.id} event={e} />
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "search" && results.length > 0 && (
        <div className="fade-in mt-3 space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-ink-500">
            {results.length} results (ranked by TF-IDF cosine similarity)
          </span>
          {results.slice(0, 15).map((e) => (
            <ResultRow key={e.id} event={e} />
          ))}
        </div>
      )}
    </div>
  );
}

function ResultRow({ event }: { event: TimelineEvent }) {
  return (
    <div className="rounded-md border border-ink-700/60 bg-ink-900/40 px-2.5 py-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[10px] text-ink-500">
          {event.occurred_at?.slice(0, 10) || "????"}
        </span>
        {event.similarity != null && (
          <span className="font-mono text-[9px] text-vic-glow/70">
            {(event.similarity * 100).toFixed(0)}% match
          </span>
        )}
      </div>
      <p className="text-xs text-ink-100">
        <span className="text-[9px] uppercase opacity-60">{event.kind.replace(/_/g, " ")}: </span>
        {event.title}
      </p>
    </div>
  );
}

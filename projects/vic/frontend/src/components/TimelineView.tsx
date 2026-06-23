import { useEffect, useMemo, useState } from "react";
import { api, type Timeline as TL } from "../lib/history-api";

const KIND_COLORS: Record<string, string> = {
  commit: "text-emerald-300 border-emerald-400/30 bg-emerald-500/5",
  decision: "text-vic-glow border-vic-glow/30 bg-vic-glow/5",
  milestone: "text-amber-300 border-amber-400/30 bg-amber-500/5",
  pr_opened: "text-sky-300 border-sky-400/30 bg-sky-500/5",
  pr_merged: "text-violet-300 border-violet-400/30 bg-violet-500/5",
  issue_opened: "text-orange-300 border-orange-400/30 bg-orange-500/5",
  chat_message: "text-cyan-300 border-cyan-400/30 bg-cyan-500/5",
  chat_session: "text-cyan-300 border-cyan-400/30 bg-cyan-500/5",
  doc_created: "text-slate-300 border-slate-500/30 bg-slate-500/5",
  doc_edit: "text-slate-300 border-slate-500/30 bg-slate-500/5",
};

export function TimelineView({ repositoryId }: { repositoryId?: string }) {
  const [timeline, setTimeline] = useState<TL | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.timeline({ repository_id: repositoryId, limit: 1000 })
      .then(setTimeline)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [repositoryId]);

  const filtered = useMemo(() => {
    if (!timeline) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return timeline.events;
    return timeline.events.filter((e) =>
      [e.title, e.body, e.kind, ...(e.tags || [])].join(" ").toLowerCase().includes(q)
    );
  }, [timeline, filter]);

  if (loading) return <div className="h-64 w-full rounded-lg shimmer" />;
  if (error) return <div className="rounded-lg border border-vic-err/40 bg-vic-err/10 p-3 text-sm text-vic-err">{error}</div>;
  if (!timeline || !timeline.events.length)
    return (
      <div className="rounded-lg border border-dashed border-ink-700 p-8 text-center text-sm text-ink-500">
        No events ingested yet. Use the ingestion panel to add a git repo, markdown docs, or notes.
      </div>
    );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-ink-100">
          Timeline — {timeline.events.length} events, {timeline.links.length} links, {timeline.clusters.length} clusters
        </h2>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter events…"
          className="w-56 rounded-lg border border-ink-700 bg-ink-900/60 px-3 py-1.5 text-xs text-ink-100 outline-none focus:border-vic-glow/40"
        />
      </div>

      {/* Timeline */}
      <div className="relative">
        <div className="absolute left-3 top-0 bottom-0 w-px bg-ink-700/60" />
        <div className="space-y-1">
          {filtered.map((e, i) => (
            <TimelineRow key={e.id} event={e} index={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

function TimelineRow({ event, index }: { event: import("../lib/history-api").TimelineEvent; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const colors = KIND_COLORS[event.kind] || "text-ink-300 border-ink-600 bg-ink-800/30";
  const date = event.occurred_at ? event.occurred_at.slice(0, 10) : "????";
  const important = event.importance >= 0.7;

  return (
    <div className="fade-in relative flex gap-3 pl-8" style={{ animationDelay: `${Math.min(index * 15, 300)}ms` }}>
      <div
        className={`absolute left-2 top-3 h-2.5 w-2.5 rounded-full border-2 border-ink-800 ${
          important ? "bg-vic-glow" : "bg-ink-600"
        }`}
      />
      <div className={`flex-1 rounded-lg border p-2.5 ${colors}`}>
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[10px] text-ink-500">{date}</span>
          <div className="flex items-center gap-1">
            {event.tags?.slice(0, 3).map((t) => (
              <span key={t} className="rounded bg-ink-900/40 px-1 py-0.5 text-[9px] text-ink-300">
                {t}
              </span>
            ))}
          </div>
        </div>
        <p
          className={`mt-1 text-xs leading-snug ${important ? "font-semibold" : ""} text-ink-100 cursor-pointer`}
          onClick={() => setExpanded((v) => !v)}
        >
          <span className="text-[9px] uppercase tracking-wider opacity-60">{event.kind.replace(/_/g, " ")}: </span>
          {event.title}
        </p>
        {expanded && event.body && (
          <p className="mt-1.5 text-[11px] leading-relaxed text-ink-300 whitespace-pre-wrap">
            {event.body.slice(0, 500)}
            {event.body.length > 500 ? "…" : ""}
          </p>
        )}
        {event.similarity != null && (
          <span className="mt-1 inline-block text-[9px] font-mono text-vic-glow/70">
            {(event.similarity * 100).toFixed(0)}% match
          </span>
        )}
      </div>
    </div>
  );
}

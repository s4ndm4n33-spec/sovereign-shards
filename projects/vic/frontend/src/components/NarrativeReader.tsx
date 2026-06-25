import { useEffect, useState } from "react";
import { api, type NarrativeEntry } from "../lib/history-api";

const KINDS: { kind: string; label: string; desc: string }[] = [
  { kind: "executive_summary", label: "Executive Summary", desc: "High-level overview of events, decisions, milestones" },
  { kind: "arch_evolution", label: "Architectural Evolution", desc: "Architecture-related changes over time" },
  { kind: "dep_evolution", label: "Dependency Evolution", desc: "Dependency additions, removals, upgrades" },
  { kind: "state_of_project", label: "State of Project", desc: "Project snapshot at a point in time" },
  { kind: "decision_tree", label: "Decision Tree", desc: "Decision lineage with supersession tracking" },
];

export function NarrativeReader({ repositoryId }: { repositoryId?: string }) {
  const [narratives, setNarratives] = useState<NarrativeEntry[]>([]);
  const [selected, setSelected] = useState<NarrativeEntry | null>(null);
  const [generating, setGenerating] = useState(false);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  useEffect(() => {
    api.narratives(repositoryId).then(setNarratives).catch(() => setNarratives([]));
  }, [repositoryId, selected]);

  async function generate(kind: string) {
    setGenerating(true);
    try {
      const n = await api.narrative({ kind, repository_id: repositoryId, since: since || undefined, until: until || undefined });
      setSelected(n);
    } catch (e) {
      console.error(e);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-ink-700/60 bg-ink-800/30 p-4">
        <h3 className="mb-3 text-sm font-semibold text-ink-100">Generate Narrative Report</h3>
        <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-ink-500">Since</span>
            <input type="date" value={since} onChange={(e) => setSince(e.target.value)} className="rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-1.5 text-xs text-ink-100" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-ink-500">Until</span>
            <input type="date" value={until} onChange={(e) => setUntil(e.target.value)} className="rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-1.5 text-xs text-ink-100" />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          {KINDS.map((k) => (
            <button
              key={k.kind}
              onClick={() => generate(k.kind)}
              disabled={generating || (k.kind === "state_of_project" && !until)}
              title={k.desc}
              className="rounded-lg border border-ink-600 bg-ink-700/40 px-3 py-2 text-xs font-medium text-ink-100 transition hover:border-vic-glow/40 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {generating ? "…" : k.label}
            </button>
          ))}
        </div>
      </div>

      {narratives.length > 0 && !selected && (
        <div className="space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-ink-500">Previously generated</span>
          {narratives.slice(0, 8).map((n) => (
            <button
              key={n.id}
              onClick={() => setSelected(n)}
              className="block w-full rounded-md border border-ink-700/60 bg-ink-900/40 px-3 py-2 text-left text-xs hover:border-vic-glow/30"
            >
              <span className="font-medium text-ink-100">{n.title}</span>
              <span className="ml-2 text-[10px] text-ink-500">{n.kind} · {n.generated_at?.slice(0, 10)}</span>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="fade-in rounded-2xl border border-vic-glow/20 bg-ink-800/40 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-vic-glow">{selected.title}</h3>
            <button onClick={() => setSelected(null)} className="text-xs text-ink-500 hover:text-ink-300">✕ close</button>
          </div>
          <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-ink-100">{selected.body}</pre>
          {selected.event_ids?.length > 0 && (
            <p className="mt-3 text-[10px] text-ink-500">Cites {selected.event_ids.length} events.</p>
          )}
        </div>
      )}
    </div>
  );
}

import { useState } from "react";

interface BioResponse {
  concept: string;
  found: boolean;
  biography?: string;
  first_mention?: { date: string; origin: string; kind: string; title: string };
  first_decision?: { date: string; title: string } | null;
  first_implementation?: { date: string; title: string } | null;
  current_status?: string;
  stats?: { total_mentions: number; decisions: number; commits: number; conversations: number; documents: number; pivots: number; graph_related: number };
  contributors?: { name: string; contributions: number }[];
  claims?: { subject: string; predicate: string; obj: string; confidence: number; inference_rule: string; evidence: { event_id: string; title: string; occurred_at: string }[] }[];
  timeline?: { date: string; kind: string; title: string; event_id: string }[];
  graph_related?: { relation: string; title: string; date: string }[];
  message?: string;
}

export function BiographyPanel({ repositoryId }: { repositoryId?: string }) {
  const [concept, setConcept] = useState("");
  const [bio, setBio] = useState<BioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    if (!concept.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/biography", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ concept: concept.trim(), repository_id: repositoryId }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setBio(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-ink-700/60 bg-ink-800/30 p-4">
      <div className="mb-3 flex items-center gap-2">
        <BookIcon />
        <h3 className="text-sm font-semibold text-ink-100">Concept Biography</h3>
      </div>
      <p className="mb-3 text-xs text-ink-300">Enter any concept name to generate its life story — first mention, decisions, implementations, contributors, and evidence chain.</p>
      <div className="flex gap-2">
        <input
          value={concept}
          onChange={(e) => setConcept(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="e.g. JGPU, registry pattern, auth…"
          className="flex-1 rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-2 text-sm text-ink-100 outline-none focus:border-vic-glow/50"
        />
        <button
          onClick={search}
          disabled={loading || !concept.trim()}
          className="rounded-lg bg-vic-glow px-4 py-2 text-xs font-semibold text-ink-950 shadow-glow transition hover:bg-cyan-300 disabled:opacity-40"
        >
          {loading ? "…" : "Generate"}
        </button>
      </div>

      {error && <div className="mt-3 rounded-lg border border-vic-err/40 bg-vic-err/10 p-2 text-xs text-vic-err">{error}</div>}

      {bio && !bio.found && (
        <div className="mt-3 rounded-lg border border-dashed border-ink-700 p-4 text-center text-xs text-ink-500">{bio.message}</div>
      )}

      {bio && bio.found && (
        <div className="fade-in mt-4 space-y-4">
          {/* Stats grid */}
          {bio.stats && (
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              <BioStat label="Mentions" value={bio.stats.total_mentions} />
              <BioStat label="Decisions" value={bio.stats.decisions} />
              <BioStat label="Commits" value={bio.stats.commits} />
              <BioStat label="Conversations" value={bio.stats.conversations} />
            </div>
          )}

          {/* Key facts */}
          <div className="space-y-1.5 rounded-lg border border-vic-glow/20 bg-vic-glow/5 p-3">
            {bio.first_mention && (
              <FactRow label="First Mention" value={`${bio.first_mention.date} (${bio.first_mention.origin})`} />
            )}
            {bio.first_decision && <FactRow label="First Decision" value={bio.first_decision.date} />}
            {bio.first_implementation && <FactRow label="First Implementation" value={bio.first_implementation.date} />}
            {bio.current_status && <FactRow label="Current Status" value={bio.current_status} highlight />}
          </div>

          {/* Contributors */}
          {bio.contributors && bio.contributors.length > 0 && (
            <div>
              <span className="text-[10px] uppercase tracking-wider text-ink-500">Primary Contributors</span>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {bio.contributors.slice(0, 5).map((c) => (
                  <span key={c.name} className="rounded-md bg-ink-700/40 px-2 py-0.5 text-xs text-ink-200">
                    {c.name} <span className="text-ink-500">({c.contributions})</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Claims with provenance */}
          {bio.claims && bio.claims.length > 0 && (
            <div>
              <span className="text-[10px] uppercase tracking-wider text-vic-glow">Evidence Chain</span>
              <div className="mt-1 space-y-2">
                {bio.claims.map((c, i) => (
                  <div key={i} className="rounded-md border border-ink-700/60 bg-ink-900/40 p-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-ink-100">
                        <span className="text-vic-glow">{c.subject}</span> {c.predicate} <span className="font-medium">{c.obj}</span>
                      </span>
                      <span className="font-mono text-[10px] text-vic-glow/70">{(c.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div className="mt-1 text-[10px] text-ink-500">Rule: {c.inference_rule}</div>
                    {c.evidence.length > 0 && (
                      <ul className="mt-1 space-y-0.5">
                        {c.evidence.slice(0, 4).map((ev, j) => (
                          <li key={j} className="text-[10px] text-ink-400">
                            • {ev.occurred_at?.slice(0, 10) || "????"} — {ev.title?.slice(0, 80)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timeline */}
          {bio.timeline && bio.timeline.length > 0 && (
            <div>
              <span className="text-[10px] uppercase tracking-wider text-ink-500">Timeline ({bio.timeline.length})</span>
              <div className="mt-1 max-h-48 space-y-0.5 overflow-y-auto">
                {bio.timeline.slice(0, 20).map((t, i) => (
                  <div key={i} className="flex gap-2 text-[11px]">
                    <span className="font-mono text-ink-500">{t.date}</span>
                    <span className="text-ink-300">[{t.kind.replace(/_/g, " ")}]</span>
                    <span className="truncate text-ink-100">{t.title}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BioStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-ink-700/60 bg-ink-900/40 p-2 text-center">
      <div className="font-mono text-sm font-semibold text-ink-100">{value}</div>
      <div className="text-[9px] uppercase tracking-wider text-ink-500">{label}</div>
    </div>
  );
}

function FactRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-ink-500">{label}</span>
      <span className={`text-xs font-medium ${highlight ? "text-vic-glow" : "text-ink-100"}`}>{value}</span>
    </div>
  );
}

function BookIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-vic-glow">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c1.052 0 2.062.18 3 .512m0-12.47A8.967 8.967 0 0 1 18 3.75c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18c-1.052 0-2.062.18-3 .512" />
    </svg>
  );
}

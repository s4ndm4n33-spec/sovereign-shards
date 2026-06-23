import { useState } from "react";

interface EvolutionResult {
  query: string;
  count: number;
  results: Record<string, unknown>[];
  claims?: { subject: string; predicate: string; obj: string; confidence: number; inference_rule: string; evidence: { event_id: string; title: string; occurred_at: string }[] }[];
}

const QUERIES = [
  { id: "reversed_decisions", label: "Reversed Decisions", desc: "Design decisions later reversed or superseded" },
  { id: "architectural_churn", label: "Architectural Churn", desc: "Modules with the most architectural change" },
  { id: "discussed_not_implemented", label: "Discussed, Not Implemented", desc: "Ideas discussed but never coded" },
  { id: "conversations_to_code", label: "Conversations → Code", desc: "Chats that resulted in implementations" },
  { id: "decision_impact", label: "Decision Impact", desc: "Decisions with greatest downstream impact" },
  { id: "top_contributors", label: "Top Contributors", desc: "Most influential contributors" },
];

export function EvolutionPanel({ repositoryId }: { repositoryId?: string }) {
  const [result, setResult] = useState<EvolutionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeQuery, setActiveQuery] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  async function runQuery(query: string) {
    setLoading(true);
    setError(null);
    setActiveQuery(query);
    try {
      const r = await fetch("/api/evolution", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, repository_id: repositoryId }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-ink-700/60 bg-ink-800/30 p-4">
      <div className="mb-3 flex items-center gap-2">
        <PulseIcon />
        <h3 className="text-sm font-semibold text-ink-100">Evolution Engine</h3>
      </div>
      <p className="mb-3 text-xs text-ink-300">Architectural reasoning queries over the knowledge graph. Each result includes an evidence chain.</p>

      <div className="flex flex-wrap gap-2">
        {QUERIES.map((q) => (
          <button
            key={q.id}
            onClick={() => runQuery(q.id)}
            disabled={loading}
            title={q.desc}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition disabled:opacity-40 ${
              activeQuery === q.id
                ? "border-vic-glow/40 bg-vic-glow/10 text-vic-glow"
                : "border-ink-600 bg-ink-700/40 text-ink-100 hover:border-vic-glow/30"
            }`}
          >
            {loading && activeQuery === q.id ? "…" : q.label}
          </button>
        ))}
      </div>

      {error && <div className="mt-3 rounded-lg border border-vic-err/40 bg-vic-err/10 p-2 text-xs text-vic-err">{error}</div>}

      {result && (
        <div className="fade-in mt-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-100">{result.count} result{result.count !== 1 ? "s" : ""}</span>
          </div>

          {/* Results */}
          {result.results.length > 0 && (
            <div className="space-y-1.5">
              {result.results.slice(0, 10).map((r, i) => (
                <div key={i} className="rounded-md border border-ink-700/60 bg-ink-900/40 p-2.5">
                  <EvolutionResultRow data={r} />
                </div>
              ))}
            </div>
          )}

          {/* Claims / Provenance */}
          {result.claims && result.claims.length > 0 && (
            <div>
              <span className="text-[10px] uppercase tracking-wider text-vic-glow">Evidence & Provenance</span>
              <div className="mt-1 space-y-2">
                {result.claims.slice(0, 5).map((c, i) => (
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
        </div>
      )}
    </div>
  );
}

function EvolutionResultRow({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([k]) => k !== "evidence");
  return (
    <div>
      {entries.slice(0, 5).map(([k, v]) => (
        <div key={k} className="flex gap-2 text-[11px]">
          <span className="text-ink-500">{k}:</span>
          <span className="truncate text-ink-100">
            {typeof v === "object" ? JSON.stringify(v).slice(0, 100) : String(v).slice(0, 120)}
          </span>
        </div>
      ))}
    </div>
  );
}

function PulseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-vic-glow">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  );
}

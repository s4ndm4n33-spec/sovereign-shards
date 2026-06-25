import { useState } from "react";

interface GraphStats {
  node_count: number;
  edge_count: number;
  edge_types: Record<string, number>;
  inferred_edges: number;
}

interface GraphNode {
  id: string;
  kind: string;
  title: string;
  occurred_at: string | null;
  _edge_type?: string;
  _confidence?: number;
  _rationale?: string;
}

const EDGE_COLORS: Record<string, string> = {
  implements: "text-emerald-300 border-emerald-400/30",
  supersedes: "text-amber-300 border-amber-400/30",
  reverses: "text-red-300 border-red-400/30",
  discusses: "text-cyan-300 border-cyan-400/30",
  documents: "text-slate-300 border-slate-500/30",
  contains: "text-sky-300 border-sky-400/30",
  precedes: "text-ink-400 border-ink-600/30",
  references: "text-violet-300 border-violet-400/30",
  motivated: "text-orange-300 border-orange-400/30",
  inspired: "text-pink-300 border-pink-400/30",
};

export function GraphExplorer({ repositoryId }: { repositoryId?: string }) {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [node, setNode] = useState<GraphNode | null>(null);
  const [neighbors, setNeighbors] = useState<GraphNode[]>([]);
  const [incoming, setIncoming] = useState<GraphNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadStats() {
    try {
      const params = new URLSearchParams();
      if (repositoryId) params.set("repository_id", repositoryId);
      const r = await fetch(`/api/graph?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setStats(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }

  async function exploreNode(id: string) {
    setLoading(true);
    setError(null);
    setSelectedId(id);
    try {
      const params = new URLSearchParams({ node_id: id });
      if (repositoryId) params.set("repository_id", repositoryId);
      const r = await fetch(`/api/graph?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setNode(data.node);
      setNeighbors(data.neighbors || []);
      setIncoming(data.incoming || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  // Load stats on mount
  useState(() => { loadStats(); });

  return (
    <div className="rounded-2xl border border-ink-700/60 bg-ink-800/30 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink-100">Knowledge Graph</h3>
        <button onClick={loadStats} className="rounded-md border border-ink-600 px-2 py-1 text-[10px] text-ink-300 hover:border-vic-glow/40">
          Refresh
        </button>
      </div>

      {stats && (
        <div className="mb-3 grid grid-cols-3 gap-2">
          <GStat label="Nodes" value={stats.node_count} />
          <GStat label="Edges" value={stats.edge_count} />
          <GStat label="Inferred" value={stats.inferred_edges} />
        </div>
      )}

      {stats && stats.edge_count > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {Object.entries(stats.edge_types).map(([type, count]) => (
            <span key={type} className={`rounded-md border px-2 py-0.5 text-[10px] ${EDGE_COLORS[type] || "text-ink-300 border-ink-600"}`}>
              {type} ({count})
            </span>
          ))}
        </div>
      )}

      {/* Node explorer */}
      <div className="flex gap-2">
        <input
          value={selectedId || ""}
          onChange={(e) => setSelectedId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && selectedId && exploreNode(selectedId)}
          placeholder="Enter an event ID to explore…"
          className="flex-1 rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-2 text-xs text-ink-100 outline-none focus:border-vic-glow/50"
        />
        <button
          onClick={() => selectedId && exploreNode(selectedId)}
          disabled={loading || !selectedId}
          className="rounded-lg bg-ink-700/40 px-3 py-2 text-xs font-medium text-ink-100 hover:bg-ink-700/60 disabled:opacity-40"
        >
          {loading ? "…" : "Explore"}
        </button>
      </div>

      {error && <div className="mt-2 text-xs text-vic-err">{error}</div>}

      {node && (
        <div className="fade-in mt-4 space-y-3">
          {/* Selected node */}
          <div className="rounded-lg border border-vic-glow/30 bg-vic-glow/5 p-3">
            <span className="text-[10px] uppercase tracking-wider text-vic-glow">{node.kind?.replace(/_/g, " ")}</span>
            <p className="mt-0.5 text-sm text-ink-100">{node.title}</p>
            <span className="font-mono text-[10px] text-ink-500">{node.occurred_at?.slice(0, 10) || "????"}</span>
          </div>

          {/* Incoming edges */}
          {incoming.length > 0 && (
            <div>
              <span className="text-[10px] uppercase tracking-wider text-ink-500">← Points to this ({incoming.length})</span>
              <div className="mt-1 space-y-1">
                {incoming.slice(0, 8).map((n) => (
                  <EdgeRow key={n.id} node={n} onClick={() => exploreNode(n.id)} />
                ))}
              </div>
            </div>
          )}

          {/* Outgoing edges */}
          {neighbors.length > 0 && (
            <div>
              <span className="text-[10px] uppercase tracking-wider text-ink-500">This points to → ({neighbors.length})</span>
              <div className="mt-1 space-y-1">
                {neighbors.slice(0, 8).map((n) => (
                  <EdgeRow key={n.id} node={n} onClick={() => exploreNode(n.id)} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-ink-700/60 bg-ink-900/40 p-2 text-center">
      <div className="font-mono text-sm font-semibold text-ink-100">{value}</div>
      <div className="text-[9px] uppercase tracking-wider text-ink-500">{label}</div>
    </div>
  );
}

function EdgeRow({ node, onClick }: { node: GraphNode; onClick: () => void }) {
  const edgeColor = EDGE_COLORS[node._edge_type || ""] || "text-ink-300 border-ink-600";
  return (
    <button
      onClick={onClick}
      className="block w-full rounded-md border border-ink-700/60 bg-ink-900/40 px-2.5 py-1.5 text-left hover:border-vic-glow/30"
    >
      <div className="flex items-center justify-between gap-2">
        <span className={`rounded border px-1 text-[9px] ${edgeColor}`}>{node._edge_type}</span>
        <span className="font-mono text-[10px] text-ink-500">{node._confidence != null ? `${(node._confidence * 100).toFixed(0)}%` : ""}</span>
      </div>
      <p className="mt-0.5 truncate text-xs text-ink-100">{node.title}</p>
      {node._rationale && <p className="text-[10px] italic text-ink-500">{node._rationale}</p>}
    </button>
  );
}

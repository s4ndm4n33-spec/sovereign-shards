import { useEffect, useState } from "react";
import { api, type StoreStats } from "../lib/history-api";

export function HistorianDashboard({ repositoryId }: { repositoryId?: string }) {
  const [stats, setStats] = useState<StoreStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.stats().then(setStats).catch(() => setStats(null)).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-2">
        <div className="h-16 w-full rounded-lg shimmer" />
      </div>
    );
  }
  if (!stats) return null;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
      <StatCard label="Events" value={stats.events} highlight />
      <StatCard label="Decisions" value={stats.decisions} />
      <StatCard label="Artifacts" value={stats.artifacts} />
      <StatCard label="Milestones" value={stats.milestones} />
      <StatCard label="Persons" value={stats.persons} />
      <StatCard label="Repos" value={stats.repositories} />
      <StatCard label="Sessions" value={stats.sessions} />
      <StatCard label="Narratives" value={stats.narratives} />
    </div>
  );
}

function StatCard({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div
      className={`rounded-lg border p-3 text-center ${
        highlight ? "border-vic-glow/30 bg-vic-glow/5" : "border-ink-700/60 bg-ink-800/30"
      }`}
    >
      <div className={`font-mono text-lg font-semibold ${highlight ? "text-vic-glow" : "text-ink-100"}`}>
        {value.toLocaleString()}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-ink-500">{label}</div>
    </div>
  );
}

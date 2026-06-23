import type { ProcessResult } from "./types";

// Existing archive-export API
export { processFiles, crawlUrls, downloadPdf, downloadJsonl } from "./archive-api";

// ---- Historian API ----

export interface TimelineEvent {
  id: string;
  repository_id: string;
  kind: string;
  source_kind: string;
  source_ref: string;
  occurred_at: string | null;
  ended_at: string | null;
  actor_id: string;
  title: string;
  body: string;
  detail_id: string;
  tags: string[];
  links: string[];
  importance: number;
  similarity?: number;
}

export interface TimelineLink {
  source: string;
  target: string;
  reason: string;
}

export interface TimelineCluster {
  id: string;
  title: string;
  event_ids: string[];
}

export interface Timeline {
  events: TimelineEvent[];
  links: TimelineLink[];
  clusters: TimelineCluster[];
  actors: Record<string, number>;
  period: { start: string | null; end: string | null } | null;
}

export interface StoreStats {
  repositories: number;
  persons: number;
  sessions: number;
  decisions: number;
  artifacts: number;
  milestones: number;
  events: number;
  narratives: number;
  earliest: string | null;
  latest: string | null;
}

export interface NarrativeEntry {
  id: string;
  repository_id: string;
  title: string;
  body: string;
  kind: string;
  period_start: string | null;
  period_end: string | null;
  query: string;
  event_ids: string[];
  generated_at: string;
}

export interface AnswerResult {
  question: string;
  answer: string;
  kind: string;
  events: TimelineEvent[];
  actor?: string;
  first_seen?: string;
  period?: { start: string | null; end: string | null };
}

const BASE = "/api";

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ error: r.statusText }));
    throw new Error(e.error || `HTTP ${r.status}`);
  }
  return r.json();
}

export const api = {
  stats: () => getJson<StoreStats>(`${BASE}/stats`),
  timeline: (params: { repository_id?: string; since?: string; until?: string; kind?: string[]; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.repository_id) q.set("repository_id", params.repository_id);
    if (params.since) q.set("since", params.since);
    if (params.until) q.set("until", params.until);
    if (params.limit) q.set("limit", String(params.limit));
    for (const k of params.kind || []) q.append("kind", k);
    return getJson<Timeline>(`${BASE}/timeline?${q}`);
  },
  search: (q: string, repository_id?: string, mode: "semantic" | "fulltext" = "semantic") => {
    const params = new URLSearchParams({ q });
    if (repository_id) params.set("repository_id", repository_id);
    params.set("mode", mode);
    return getJson<TimelineEvent[]>(`${BASE}/search?${params}`);
  },
  ask: (question: string, repository_id?: string) => postJson<AnswerResult>(`${BASE}/ask`, { question, repository_id }),
  narrative: (opts: { kind: string; repository_id?: string; since?: string; until?: string; at_date?: string; query?: string }) =>
    postJson<NarrativeEntry>(`${BASE}/narrative`, opts),
  narratives: (repository_id?: string) =>
    getJson<NarrativeEntry[]>(`${BASE}/narratives${repository_id ? `?repository_id=${repository_id}` : ""}`),
  decisions: (repository_id?: string) =>
    getJson<Record<string, unknown>[]>(`${BASE}/decisions${repository_id ? `?repository_id=${repository_id}` : ""}`),
  persons: (repository_id?: string) =>
    getJson<Record<string, unknown>[]>(`${BASE}/persons${repository_id ? `?repository_id=${repository_id}` : ""}`),
  ingestGit: (path: string, repository_id?: string) =>
    postJson<{ repository_id: string; commits: number }>(`${BASE}/ingest/git`, { path, repository_id }),
  ingestMarkdown: (path: string, repository_id: string) =>
    postJson<{ repository_id: string; title: string }>(`${BASE}/ingest/markdown`, { path, repository_id }),
  ingestNotes: (path: string, repository_id: string) =>
    postJson<{ repository_id: string; notes: number }>(`${BASE}/ingest/notes`, { path, repository_id }),
};

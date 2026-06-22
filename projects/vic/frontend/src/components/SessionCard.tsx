import { useState } from "react";
import type { SessionEntry } from "../lib/types";
import { ProviderBadge } from "./ProviderBadge";

interface SessionCardProps {
  session: SessionEntry;
}

function Chip({ label, items, tone }: { label: string; items: string[]; tone: string }) {
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  const shown = open ? items : items.slice(0, 1);
  return (
    <div className="mt-3 text-xs">
      <div className="mb-1 flex items-center gap-2">
        <span className={`font-medium uppercase tracking-wider ${tone}`}>{label}</span>
        <span className="rounded-full bg-ink-700/60 px-1.5 py-0.5 font-mono text-[10px] text-ink-300">
          {items.length}
        </span>
        {items.length > 1 && (
          <button
            onClick={() => setOpen((v) => !v)}
            className="text-[10px] text-vic-glow hover:underline"
          >
            {open ? "hide" : `+${items.length - 1} more`}
          </button>
        )}
      </div>
      <ul className="space-y-1">
        {shown.map((item, i) => (
          <li key={i} className="leading-snug text-ink-100">
            • {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SessionCard({ session }: SessionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const hasExtras =
    session.decisions.length +
      session.bugs.length +
      session.fixes.length +
      session.architecture.length +
      session.open_questions.length >
    0;

  return (
    <article
      className={`session-card fade-in rounded-xl border border-ink-700/60 bg-ink-800/40 p-4 hover:border-vic-glow/30 hover:bg-ink-800/60`}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-vic-glow/80">#{session.session}</span>
          <span className="font-mono text-[11px] text-ink-300">{session.date}</span>
          <ProviderBadge provider={session.provider} />
        </div>
        <span className="text-[11px] text-ink-500">
          {session.message_count} message{session.message_count === 1 ? "" : "s"}
        </span>
      </div>
      <h3 className="text-sm font-semibold leading-snug text-ink-100">
        {session.title || "(untitled)"}
      </h3>
      <p className={`mt-2 text-xs leading-relaxed text-ink-300 ${expanded ? "" : "line-clamp-3"}`}>
        {session.summary || "(no summary extracted)"}
      </p>
      {session.summary.length > 200 && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 text-[11px] text-vic-glow hover:underline"
        >
          {expanded ? "show less" : "show full"}
        </button>
      )}

      {hasExtras && (
        <>
          <Chip label="Decisions" items={session.decisions} tone="text-vic-glow" />
          <Chip label="Problems" items={session.bugs} tone="text-vic-err" />
          <Chip label="Fixes" items={session.fixes} tone="text-emerald-300" />
          <Chip label="Architecture" items={session.architecture} tone="text-vic-accent" />
          <Chip label="Open Questions" items={session.open_questions} tone="text-vic-warn" />
        </>
      )}
    </article>
  );
}

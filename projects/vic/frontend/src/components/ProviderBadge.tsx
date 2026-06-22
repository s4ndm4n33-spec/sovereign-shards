import type { Provider } from "../lib/types";

const STYLES: Record<string, { bg: string; text: string; ring: string; label: string }> = {
  gemini: {
    bg: "bg-sky-500/10",
    text: "text-sky-300",
    ring: "ring-sky-400/30",
    label: "Gemini",
  },
  chatgpt: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-300",
    ring: "ring-emerald-400/30",
    label: "ChatGPT",
  },
  claude: {
    bg: "bg-orange-500/10",
    text: "text-orange-300",
    ring: "ring-orange-400/30",
    label: "Claude",
  },
  unknown: {
    bg: "bg-slate-500/10",
    text: "text-slate-300",
    ring: "ring-slate-500/30",
    label: "Unknown",
  },
};

export function ProviderBadge({ provider }: { provider: Provider }) {
  const s = STYLES[provider] ?? STYLES.unknown;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${s.bg} ${s.text} ring-1 ${s.ring} select-none`}
    >
      <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {s.label}
    </span>
  );
}

export function ProviderBadges({ providers }: { providers: Provider[] }) {
  if (!providers.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {providers.map((p) => (
        <ProviderBadge key={p} provider={p} />
      ))}
    </div>
  );
}

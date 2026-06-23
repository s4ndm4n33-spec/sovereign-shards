import { useState } from "react";

interface LinkInputProps {
  onSubmit: (urls: string[]) => void;
  disabled?: boolean;
}

const HOST_HINTS = ["chatgpt.com/share", "claude.ai/share", "gemini.google.com/share"];

export function LinkInput({ onSubmit, disabled }: LinkInputProps) {
  const [value, setValue] = useState("");
  const [urls, setUrls] = useState<string[]>([]);

  const add = () => {
    const v = value.trim();
    if (!v) return;
    // Accept space/newline separated lists
    const parts = v.split(/[\s\n]+/).map((s) => s.trim()).filter(Boolean);
    setUrls((prev) => {
      const next = [...prev];
      for (const p of parts) {
        if (!next.includes(p)) next.push(p);
      }
      return next;
    });
    setValue("");
  };

  const remove = (u: string) => setUrls((prev) => prev.filter((x) => x !== u));

  const submit = () => {
    // Include any unstaged value too
    const pending = value.trim();
    const final = pending
      ? [...urls, ...pending.split(/[\s\n]+/).map((s) => s.trim()).filter(Boolean)]
      : urls;
    const dedup = Array.from(new Set(final));
    if (!dedup.length) return;
    onSubmit(dedup);
    setValue("");
    setUrls([]);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      add();
    }
  };

  return (
    <div className="rounded-2xl border border-ink-700/60 bg-ink-800/30 p-4">
      <div className="mb-2 flex items-center gap-2">
        <LinkIcon />
        <h3 className="text-sm font-semibold text-ink-100">Crawl a shared chat link</h3>
        <span className="rounded-full bg-ink-700/50 px-2 py-0.5 text-[10px] text-ink-300">beta</span>
      </div>
      <p className="mb-3 text-xs text-ink-300">
        Paste a public share URL. V.I.C. fetches the page, renders it, and extracts the same structured data as an upload.
      </p>
      <div className="flex gap-2">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled}
          placeholder="https://chatgpt.com/share/…  ·  https://claude.ai/share/…  ·  https://gemini.google.com/share/…"
          className="flex-1 rounded-lg border border-ink-600 bg-ink-900/60 px-3 py-2 text-sm text-ink-100 outline-none placeholder:text-ink-500 focus:border-vic-glow/50 disabled:opacity-50"
        />
        <button
          type="button"
          onClick={add}
          disabled={disabled || !value.trim()}
          className="rounded-lg border border-ink-600 bg-ink-700/40 px-3 py-2 text-xs font-medium text-ink-100 transition hover:border-vic-glow/40 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Add
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={disabled || (!urls.length && !value.trim())}
          className="rounded-lg bg-vic-glow px-4 py-2 text-xs font-semibold text-ink-950 shadow-glow transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Crawl
        </button>
      </div>
      {urls.length > 0 && (
        <ul className="mt-3 space-y-1">
          {urls.map((u) => (
            <li key={u} className="flex items-center justify-between rounded-md bg-ink-900/50 px-2 py-1 text-xs">
              <span className="truncate text-ink-100">{u}</span>
              <button
                onClick={() => remove(u)}
                className="ml-2 text-ink-500 hover:text-vic-err"
                aria-label={`Remove ${u}`}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {HOST_HINTS.map((h) => (
          <span key={h} className="rounded-md bg-ink-700/40 px-2 py-0.5 text-[10px] text-ink-300">
            {h}
          </span>
        ))}
      </div>
    </div>
  );
}

function LinkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-vic-glow">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m13.35-.688a4.5 4.5 0 0 0-1.242-7.244l-4.5-4.5a4.5 4.5 0 0 0-6.364 6.364l1.757 1.757"
      />
    </svg>
  );
}

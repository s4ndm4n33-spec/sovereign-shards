import { useCallback, useState } from "react";
import { Dropzone } from "./components/Dropzone";
import { LinkInput } from "./components/LinkInput";
import { ProgressBar } from "./components/ProgressBar";
import { ResultsPanel } from "./components/ResultsPanel";
import { crawlUrls, processFiles } from "./lib/api";
import type { ProcessResult } from "./lib/types";

type Stage = "idle" | "working" | "done" | "error";

export default function App() {
  const [stage, setStage] = useState<Stage>("idle");
  const [progress, setProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState("");
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);

  const handleFiles = useCallback(async (files: File[]) => {
    setStagedFiles(files);
    setStage("working");
    setError(null);
    setProgress(0);
    setProgressLabel("Preparing…");
    try {
      const res = await processFiles(files, (pct, label) => {
        setProgress(pct);
        setProgressLabel(label);
      });
      setResult(res);
      setStage("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Processing failed");
      setStage("error");
    }
  }, []);

  const handleUrls = useCallback(async (urls: string[]) => {
    setStagedFiles([]);
    setStage("working");
    setError(null);
    setProgress(0);
    setProgressLabel("Fetching shared chat…");
    try {
      const res = await crawlUrls(urls, (pct, label) => {
        setProgress(pct);
        setProgressLabel(label);
      });
      setResult(res);
      setStage("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Crawl failed");
      setStage("error");
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setStagedFiles([]);
    setStage("idle");
    setProgress(0);
    setError(null);
  }, []);

  return (
    <div className="bg-grid min-h-screen">
      <header className="mx-auto max-w-6xl px-6 pb-4 pt-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Logo />
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-ink-100">
                V.I.C. <span className="text-vic-glow">— Value In Conversation</span>
              </h1>
              <p className="text-[11px] uppercase tracking-widest text-ink-500">
                Bulk AI chat archive · sovereign by design
              </p>
            </div>
          </div>
          <div className="hidden items-center gap-2 text-[11px] text-ink-500 sm:flex">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
            No auth · No database · Nothing leaves your machine
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-20">
        {stage !== "done" && (
          <section className="space-y-6">
            <Dropzone onFiles={handleFiles} disabled={stage === "working"} />

            <LinkInput onSubmit={handleUrls} disabled={stage === "working"} />

            {stagedFiles.length > 0 && (
              <div className="rounded-xl border border-ink-700/60 bg-ink-800/30 p-3">
                <div className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">
                  Staged files ({stagedFiles.length})
                </div>
                <ul className="grid grid-cols-1 gap-1 text-xs text-ink-100 sm:grid-cols-2">
                  {stagedFiles.slice(0, 12).map((f, i) => (
                    <li key={i} className="flex items-center gap-2 truncate">
                      <span className="text-vic-glow">›</span>
                      <span className="truncate">{f.name}</span>
                      <span className="font-mono text-ink-500">{formatBytes(f.size)}</span>
                    </li>
                  ))}
                  {stagedFiles.length > 12 && (
                    <li className="text-ink-500">…and {stagedFiles.length - 12} more</li>
                  )}
                </ul>
              </div>
            )}

            {stage === "working" && (
              <div className="rounded-xl border border-ink-700/60 bg-ink-800/30 p-4">
                <ProgressBar pct={progress} label={progressLabel} />
              </div>
            )}

            {stage === "error" && (
              <div className="rounded-xl border border-vic-err/40 bg-vic-err/10 p-4 text-sm text-vic-err">
                <div className="mb-1 font-semibold">Processing failed</div>
                <div className="font-mono text-xs">{error}</div>
                <button
                  onClick={reset}
                  className="mt-3 rounded-lg border border-vic-err/40 px-3 py-1.5 text-xs hover:bg-vic-err/10"
                >
                  Try again
                </button>
              </div>
            )}

            <FeatureGrid />
          </section>
        )}

        {stage === "done" && result && <ResultsPanel result={result} onReset={reset} />}
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-8 text-center text-[11px] text-ink-500">
        V.I.C. processes every conversation locally — your prompts, code, and decisions are never uploaded to a third party.
      </footer>
    </div>
  );
}

function Logo() {
  return (
    <div className="relative">
      <div className="absolute inset-0 -z-10 rounded-xl bg-vic-glow/30 blur-xl" />
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-vic-accent to-vic-glow text-ink-950 shadow-glow">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h8M8 14h5m-8 6h11a3 3 0 0 0 3-3V7a3 3 0 0 0-3-3H6a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3Z" />
        </svg>
      </div>
    </div>
  );
}

function FeatureGrid() {
  const items = [
    { title: "Auto-detect", body: "Taketout ZIP, conversations.json, or Claude JSON — no manual selection." },
    { title: "Cross-provider timeline", body: "Sessions from Gemini, ChatGPT, and Claude merged chronologically." },
    { title: "Cliffnotes", body: "One-paragraph summary per session plus decisions, bugs, fixes, open questions." },
    { title: "Two exports", body: "Structured PDF report with reportlab, plus machine-readable archive.jsonl." },
  ];
  return (
    <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((it) => (
        <div
          key={it.title}
          className="rounded-xl border border-ink-700/60 bg-ink-800/30 p-4 transition hover:border-vic-glow/30"
        >
          <h3 className="mb-1 text-sm font-semibold text-vic-glow">{it.title}</h3>
          <p className="text-xs leading-relaxed text-ink-300">{it.body}</p>
        </div>
      ))}
    </section>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)}GB`;
}

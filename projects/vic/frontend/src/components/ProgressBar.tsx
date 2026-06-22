interface ProgressBarProps {
  pct: number;
  label: string;
}

export function ProgressBar({ pct, label }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div className="w-full">
      <div className="mb-2 flex items-center justify-between text-xs text-ink-300">
        <span>{label}</span>
        <span className="font-mono text-vic-glow">{clamped}%</span>
      </div>
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-ink-700/60">
        <div
          className="absolute left-0 top-0 h-full rounded-full bg-gradient-to-r from-vic-accent to-vic-glow transition-[width] duration-300 ease-out"
          style={{ width: `${clamped}%` }}
        >
          <div className="absolute inset-0 rounded-full bg-gradient-to-r from-transparent via-white/30 to-transparent opacity-60" />
        </div>
      </div>
    </div>
  );
}

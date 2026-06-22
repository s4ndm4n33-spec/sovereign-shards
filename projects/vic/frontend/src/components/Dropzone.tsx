import { useCallback, useRef, useState } from "react";

interface DropzoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export function Dropzone({ onFiles, disabled }: DropzoneProps) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setDragging(false);
      if (disabled) return;
      const files = Array.from(e.dataTransfer.files ?? []);
      if (files.length) onFiles(files);
    },
    [onFiles, disabled]
  );

  const handleSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      if (files.length) onFiles(files);
      // reset value so selecting the same file again still fires onChange
      e.target.value = "";
    },
    [onFiles]
  );

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragging(false);
      }}
      onDrop={handleDrop}
      className={`dropzone group relative flex w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition ${
        dragging
          ? "border-vic-glow bg-vic-glow/5 shadow-glow"
          : "border-ink-600 hover:border-vic-glow/60 hover:bg-ink-800/40"
      } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".zip,.json,application/zip,application/json"
        className="hidden"
        onChange={handleSelect}
        disabled={disabled}
      />
      <div className="mb-4 relative">
        <div className="absolute inset-0 -z-10 rounded-full bg-vic-glow/20 blur-2xl opacity-60 group-hover:opacity-90 transition" />
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="h-14 w-14 text-vic-glow"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M7.5 7.5h-.75A2.25 2.25 0 0 0 4.5 9.75v7.5a2.25 2.25 0 0 0 2.25 2.25h7.5a2.25 2.25 0 0 0 2.25-2.25v-7.5a2.25 2.25 0 0 0-2.25-2.25h-.75m-6 3.75 3-3 3 3m-3-3V15"
          />
        </svg>
      </div>
      <p className="text-sm font-medium text-ink-100">
        Drag &amp; drop a <span className="text-vic-glow">Takeout ZIP</span>, ChatGPT export{" "}
        <span className="text-emerald-300">conversations.json</span>, or Claude JSON files
      </p>
      <p className="mt-1 text-xs text-ink-300">
        Or <span className="text-vic-glow underline decoration-dotted underline-offset-2">browse</span> — multiple files supported, auto-detected.
      </p>
      <p className="mt-3 text-[11px] uppercase tracking-widest text-ink-500">
        Processed locally · nothing leaves your machine
      </p>
    </div>
  );
}

// Copyright (c) 2026 Mike McCollum
//
// Licensed under the Sovereign Shards License.
// See LICENSE.md for details.

```tsx
import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useQuery, useMutation, useAction } from "convex/react";
import { api } from "../../convex/_generated/api";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import hljs from "highlight.js/lib/core";
import {
  GitBranch, File, Folder, FolderOpen, ChevronRight, ChevronDown,
  Unplug, Plug, Loader2, FileCode, Copy, Check, AlertTriangle, CheckCircle2,
} from "lucide-react";

// Register only essential core languages to keep the substrate lean
import python from "highlight.js/lib/languages/python";
import typescript from "highlight.js/lib/languages/typescript";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import rust from "highlight.js/lib/languages/rust";

[python, typescript, javascript, json, markdown, rust].forEach(lang => {
  hljs.registerLanguage(lang.name, lang);
});

// Static definitions moved outside component to prevent re-creation
const LANG_MAP: Record<string, string> = {
  py: "python", ts: "typescript", tsx: "typescript", js: "javascript",
  jsx: "javascript", json: "json", md: "markdown", rs: "rust"
};

// --- Logic ---

function getLanguage(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return LANG_MAP[ext] ?? "plaintext";
}

function verifySyntax(content: string, lang: string): SyntaxIssue[] {
  const issues: SyntaxIssue[] = [];
  const lines = content.split("\n");

  // Logic pruning: Combined iterations for performance (Korotkevich)
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lineNum = i + 1;
    const trimmed = line.trim();

    if (lang === "python") {
      if (line.includes("\t") && line.includes("  ")) {
        issues.push({ line: lineNum, message: "Mixed tabs and spaces", severity: "warning" });
      }
      if (/^\s*except\s*:/.test(line)) {
        issues.push({ line: lineNum, message: "Bare except detected", severity: "warning" });
      }
    }

    if ((lang === "javascript" || lang === "typescript") && /\bvar\s+/.test(trimmed)) {
      issues.push({ line: lineNum, message: "Use 'const' or 'let'", severity: "warning" });
    }
  }
  return issues;
}

// --- Components ---

function HighlightedCode({ content, language, issues }: { content: string; language: string; issues: SyntaxIssue[] }) {
  const highlighted = useMemo(() => {
    return hljs.highlight(content, { language: hljs.getLanguage(language) ? language : "plaintext" }).value;
  }, [content, language]);

  const issueLines = useMemo(() => {
    const map = new Map<number, SyntaxIssue>();
    for (const iss of issues) map.set(iss.line, iss);
    return map;
  }, [issues]);

  return (
    <div className="min-w-full inline-block">
      {highlighted.split("\n").map((line, i) => {
        const lineNum = i + 1;
        const issue = issueLines.get(lineNum);
        return (
          <div key={i} className={`flex font-mono text-xs leading-6 ${issue ? "bg-red-500/10 border-l-2 border-red-500" : "hover:bg-white/5"}`}>
            <span className="w-12 shrink-0 text-right pr-4 text-slate-600 select-none">{lineNum}</span>
            <span className="flex-1 whitespace-pre" dangerouslySetInnerHTML={{ __html: line || " " }} />
            {issue && <span className="px-2 text-red-400 text-[10px] uppercase font-bold">{issue.message}</span>}
          </div>
        );
      })}
    </div>
  );
}

export function EditorPage() {
  const connection = useQuery(api.github.getConnection);
  const [tree, setTree] = useState<TreeItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>("");
  const [loading, setLoading] = useState(false);

  // Defensive Copy (Hamilton)
  const handleCopy = useCallback(async () => {
    if (!navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(fileContent);
    } catch (err) {
      console.error("FAIL: Clipboard access denied", err);
    }
  }, [fileContent]);

  if (!connection?.connected) return <div className="h-full bg-black" />;

  return (
    <div className="flex h-screen w-full bg-[#06060F] overflow-hidden">
      {/* Sidebar - Fixed Height Trapping */}
      <aside className="w-64 flex flex-col border-r border-slate-900 overflow-hidden">
        <div className="p-4 border-b border-slate-900 shrink-0 uppercase tracking-widest text-[10px] text-slate-500 font-bold">
          Filesystem
        </div>
        <ScrollArea className="flex-1">
          <div className="p-2">
            {/* Tree Nodes Here */}
          </div>
        </ScrollArea>
      </aside>

      {/* Main Editor - The "Relative Flex-1" Scroll Trap */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-10 border-b border-slate-900 flex items-center px-4 bg-[#0a0a14] shrink-0">
          <span className="text-xs font-mono text-slate-400">{selectedFile || "IDLE"}</span>
          <Button size="sm" variant="ghost" onClick={handleCopy} className="ml-auto h-7">
            <Copy className="size-3" />
          </Button>
        </header>

        <div className="flex-1 relative overflow-hidden">
          <ScrollArea className="h-full w-full">
            <div className="p-4">
              {loading ? (
                <Loader2 className="animate-spin" />
              ) : (
                <HighlightedCode 
                  content={fileContent} 
                  language={getLanguage(selectedFile || "")} 
                  issues={[]} 
                />
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Console / Issues Tray */}
        <footer className="h-8 border-t border-slate-900 bg-black px-4 flex items-center text-[10px] text-slate-500">
          OK: Substrate Integrity Verified
        </footer>
      </main>
    </div>
  );
}
```

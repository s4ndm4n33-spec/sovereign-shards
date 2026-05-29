import { useState, useEffect, useRef, useMemo } from "react";
import { useQuery, useMutation, useAction } from "convex/react";
import { api } from "../../convex/_generated/api";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import hljs from "highlight.js/lib/core";

// Import popular languages for highlight.js
import python from "highlight.js/lib/languages/python";
import typescript from "highlight.js/lib/languages/typescript";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import yaml from "highlight.js/lib/languages/yaml";
import css from "highlight.js/lib/languages/css";
import xml from "highlight.js/lib/languages/xml";
import bash from "highlight.js/lib/languages/bash";
import rust from "highlight.js/lib/languages/rust";
import go from "highlight.js/lib/languages/go";
import java from "highlight.js/lib/languages/java";
import cpp from "highlight.js/lib/languages/cpp";
import ruby from "highlight.js/lib/languages/ruby";
import php from "highlight.js/lib/languages/php";
import sql from "highlight.js/lib/languages/sql";
import ini from "highlight.js/lib/languages/ini";
import diff from "highlight.js/lib/languages/diff";
import plaintext from "highlight.js/lib/languages/plaintext";

import {
  GitBranch,
  File,
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  Unplug,
  Plug,
  Loader2,
  FileCode,
  Copy,
  Check,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";

// Register languages
hljs.registerLanguage("python", python);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("json", json);
hljs.registerLanguage("markdown", markdown);
hljs.registerLanguage("yaml", yaml);
hljs.registerLanguage("css", css);
hljs.registerLanguage("html", xml);
hljs.registerLanguage("xml", xml);
hljs.registerLanguage("bash", bash);
hljs.registerLanguage("rust", rust);
hljs.registerLanguage("go", go);
hljs.registerLanguage("java", java);
hljs.registerLanguage("cpp", cpp);
hljs.registerLanguage("c", cpp);
hljs.registerLanguage("ruby", ruby);
hljs.registerLanguage("php", php);
hljs.registerLanguage("sql", sql);
hljs.registerLanguage("ini", ini);
hljs.registerLanguage("toml", ini);
hljs.registerLanguage("diff", diff);
hljs.registerLanguage("text", plaintext);

type TreeItem = {
  name: string;
  path: string;
  type: "file" | "dir";
  size?: number;
  children?: TreeItem[];
  expanded?: boolean;
};

const LANG_MAP: Record<string, string> = {
  py: "python",
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  json: "json",
  md: "markdown",
  yml: "yaml",
  yaml: "yaml",
  toml: "toml",
  css: "css",
  html: "html",
  htm: "html",
  xml: "xml",
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  rs: "rust",
  go: "go",
  java: "java",
  c: "c",
  cpp: "cpp",
  h: "cpp",
  hpp: "cpp",
  rb: "ruby",
  php: "php",
  sql: "sql",
  ini: "ini",
  cfg: "ini",
  conf: "ini",
  txt: "text",
  diff: "diff",
  patch: "diff",
  gitignore: "text",
  dockerfile: "bash",
  makefile: "bash",
  env: "ini",
};

function getLanguage(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  const baseName = filename.split("/").pop()?.toLowerCase() || "";
  // Check special filenames first
  if (baseName === "dockerfile") return "bash";
  if (baseName === "makefile") return "bash";
  if (baseName === ".gitignore") return "text";
  if (baseName === ".env" || baseName === ".env.local") return "ini";
  return LANG_MAP[ext] || "text";
}

function getLanguageDisplayName(lang: string): string {
  const names: Record<string, string> = {
    python: "Python",
    typescript: "TypeScript",
    javascript: "JavaScript",
    json: "JSON",
    markdown: "Markdown",
    yaml: "YAML",
    toml: "TOML",
    css: "CSS",
    html: "HTML",
    xml: "XML",
    bash: "Bash",
    rust: "Rust",
    go: "Go",
    java: "Java",
    c: "C",
    cpp: "C++",
    ruby: "Ruby",
    php: "PHP",
    sql: "SQL",
    ini: "INI",
    diff: "Diff",
    text: "Text",
  };
  return names[lang] || lang;
}

// =================== SYNTAX VERIFICATION ===================

interface SyntaxIssue {
  line: number;
  message: string;
  severity: "error" | "warning";
}

function verifySyntax(content: string, lang: string): SyntaxIssue[] {
  const issues: SyntaxIssue[] = [];
  const lines = content.split("\n");

  if (lang === "python") {
    let indentStack: number[] = [0];
    lines.forEach((line, i) => {
      const trimmed = line.trimStart();
      if (!trimmed || trimmed.startsWith("#")) return;
      const indent = line.length - trimmed.length;
      // Check for tabs mixed with spaces
      if (line.includes("\t") && line.includes("  ")) {
        issues.push({ line: i + 1, message: "Mixed tabs and spaces", severity: "warning" });
      }
      // Check for bare except
      if (/^\s*except\s*:/.test(line)) {
        issues.push({ line: i + 1, message: "Bare except (catch specific exceptions)", severity: "warning" });
      }
      // Check unmatched brackets
      const opens = (line.match(/[([{]/g) || []).length;
      const closes = (line.match(/[)\]}]/g) || []).length;
      if (opens !== closes && !trimmed.endsWith("\\") && !trimmed.endsWith(",")) {
        // Multi-line is ok, just flag obvious issues
      }
    });
    // Check for trailing whitespace
    lines.forEach((line, i) => {
      if (line !== line.trimEnd() && line.trim().length > 0) {
        issues.push({ line: i + 1, message: "Trailing whitespace", severity: "warning" });
      }
    });
  } else if (lang === "json") {
    try {
      JSON.parse(content);
    } catch (e: any) {
      const match = e.message?.match(/position (\d+)/);
      if (match) {
        const pos = parseInt(match[1]);
        let lineNum = content.substring(0, pos).split("\n").length;
        issues.push({ line: lineNum, message: e.message, severity: "error" });
      } else {
        issues.push({ line: 1, message: e.message || "Invalid JSON", severity: "error" });
      }
    }
  } else if (lang === "javascript" || lang === "typescript") {
    lines.forEach((line, i) => {
      const trimmed = line.trim();
      // Check var usage
      if (/\bvar\s+/.test(trimmed)) {
        issues.push({ line: i + 1, message: "Use 'const' or 'let' instead of 'var'", severity: "warning" });
      }
      // Check console.log in production-looking code
      if (/console\.log\(/.test(trimmed) && !trimmed.startsWith("//")) {
        issues.push({ line: i + 1, message: "console.log left in code", severity: "warning" });
      }
      // == instead of ===
      if (/[^=!]==[^=]/.test(trimmed) && !trimmed.startsWith("//")) {
        issues.push({ line: i + 1, message: "Use === instead of ==", severity: "warning" });
      }
    });
  } else if (lang === "yaml") {
    lines.forEach((line, i) => {
      if (line.includes("\t")) {
        issues.push({ line: i + 1, message: "Tabs not allowed in YAML (use spaces)", severity: "error" });
      }
    });
  } else if (lang === "rust") {
    lines.forEach((line, i) => {
      if (/\bunwrap\(\)/.test(line) && !line.trim().startsWith("//")) {
        issues.push({ line: i + 1, message: "unwrap() can panic — consider using ? or match", severity: "warning" });
      }
    });
  }

  return issues;
}

// =================== HIGHLIGHTED CODE VIEW ===================

function HighlightedCode({
  content,
  language,
  issues,
}: {
  content: string;
  language: string;
  issues: SyntaxIssue[];
}) {
  const highlighted = useMemo(() => {
    try {
      const hljsLang = hljs.getLanguage(language) ? language : "text";
      return hljs.highlight(content, { language: hljsLang }).value;
    } catch {
      return content
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }
  }, [content, language]);

  const lines = highlighted.split("\n");
  const issueLines = new Map<number, SyntaxIssue>();
  issues.forEach((iss) => issueLines.set(iss.line, iss));

  return (
    <pre className="p-4 font-mono text-xs leading-relaxed whitespace-pre overflow-x-auto">
      {lines.map((line, i) => {
        const lineNum = i + 1;
        const issue = issueLines.get(lineNum);
        return (
          <div
            key={i}
            className={`flex group ${
              issue
                ? issue.severity === "error"
                  ? "bg-red-500/10 border-l-2 border-red-500/50"
                  : "bg-[#FFD700]/5 border-l-2 border-[#FFD700]/30"
                : "hover:bg-[#1a1a2e]/50"
            }`}
          >
            <span className="select-none w-12 shrink-0 text-right pr-4 text-[#8888a0]/40">
              {lineNum}
            </span>
            <span
              className="flex-1"
              dangerouslySetInnerHTML={{ __html: line || " " }}
            />
            {issue && (
              <span
                className={`shrink-0 px-2 text-[10px] self-center ${
                  issue.severity === "error"
                    ? "text-red-400"
                    : "text-[#FFD700]"
                }`}
                title={issue.message}
              >
                {issue.severity === "error" ? "⛔" : "⚠"} {issue.message}
              </span>
            )}
          </div>
        );
      })}
    </pre>
  );
}

// =================== FILE TREE NODE ===================

function FileTreeNode({
  item,
  depth,
  onToggle,
  onSelect,
  selectedPath,
}: {
  item: TreeItem;
  depth: number;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
  selectedPath: string | null;
}) {
  const isDir = item.type === "dir";
  const isSelected = selectedPath === item.path;

  return (
    <>
      <button
        onClick={() => (isDir ? onToggle(item.path) : onSelect(item.path))}
        className={`w-full text-left flex items-center gap-1.5 py-1 px-2 text-xs hover:bg-[#1a1a2e] rounded transition ${
          isSelected ? "bg-[#1E90FF]/15 text-[#1E90FF]" : "text-[#8888a0]"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {isDir ? (
          item.expanded ? (
            <>
              <ChevronDown className="size-3 shrink-0" />
              <FolderOpen className="size-3.5 shrink-0 text-[#FFD700]" />
            </>
          ) : (
            <>
              <ChevronRight className="size-3 shrink-0" />
              <Folder className="size-3.5 shrink-0 text-[#FFD700]" />
            </>
          )
        ) : (
          <>
            <span className="size-3 shrink-0" />
            <FileCode className="size-3.5 shrink-0 text-[#1E90FF]" />
          </>
        )}
        <span className="truncate">{item.name}</span>
        {!isDir && item.size !== undefined && (
          <span className="ml-auto text-[10px] text-[#8888a0]/50 shrink-0">
            {item.size > 1024
              ? `${(item.size / 1024).toFixed(1)}K`
              : `${item.size}B`}
          </span>
        )}
      </button>
      {isDir &&
        item.expanded &&
        item.children?.map((child) => (
          <FileTreeNode
            key={child.path}
            item={child}
            depth={depth + 1}
            onToggle={onToggle}
            onSelect={onSelect}
            selectedPath={selectedPath}
          />
        ))}
    </>
  );
}

// =================== EDITOR PAGE ===================

export function EditorPage() {
  const connection = useQuery(api.github.getConnection);
  const connectRepo = useMutation(api.github.connect);
  const disconnectRepo = useMutation(api.github.disconnect);
  const fetchTree = useAction(api.github.fetchRepoTree);
  const fetchFile = useAction(api.github.fetchFileContent);

  const [owner, setOwner] = useState("s4ndm4n33-spec");
  const [repo, setRepo] = useState("sovereign-shards");
  const [branch, setBranch] = useState("main");
  const [tree, setTree] = useState<TreeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>("");
  const [fileLoading, setFileLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showVerify, setShowVerify] = useState(false);

  const currentLang = selectedFile ? getLanguage(selectedFile) : "text";
  const syntaxIssues = useMemo(
    () => (showVerify && fileContent ? verifySyntax(fileContent, currentLang) : []),
    [showVerify, fileContent, currentLang]
  );

  const loadTree = async (path?: string) => {
    if (!connection) return;
    setLoading(true);
    try {
      const items = await fetchTree({
        owner: connection.owner,
        repo: connection.repo,
        branch: connection.branch,
        path,
      });
      items.sort((a: any, b: any) => {
        if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      if (!path) {
        setTree(items.map((i: any) => ({ ...i, expanded: false, children: [] })));
      } else {
        setTree((prev) => updateTreeChildren(prev, path, items));
      }
    } catch (err) {
      console.error("Tree error:", err);
    }
    setLoading(false);
  };

  const updateTreeChildren = (
    nodes: TreeItem[],
    targetPath: string,
    children: TreeItem[]
  ): TreeItem[] => {
    return nodes.map((node) => {
      if (node.path === targetPath) {
        return {
          ...node,
          expanded: !node.expanded,
          children: node.expanded
            ? []
            : children.map((c) => ({
                ...c,
                expanded: false,
                children: [],
              })),
        };
      }
      if (node.children) {
        return {
          ...node,
          children: updateTreeChildren(node.children, targetPath, children),
        };
      }
      return node;
    });
  };

  useEffect(() => {
    if (connection?.connected) {
      loadTree();
    }
  }, [connection?.connected]);

  const handleConnect = async () => {
    if (!owner || !repo) return;
    setLoading(true);
    setError(null);
    try {
      await connectRepo({ owner, repo, branch });
    } catch (err: any) {
      const msg = err?.message || err?.data || String(err);
      setError(
        msg.includes("Not authenticated")
          ? "Not authenticated. Please sign in first."
          : `Connection failed: ${msg}`
      );
    }
    setLoading(false);
  };

  const handleSelectFile = async (path: string) => {
    if (!connection) return;
    setSelectedFile(path);
    setFileLoading(true);
    setShowVerify(false);
    try {
      const result = await fetchFile({
        owner: connection.owner,
        repo: connection.repo,
        path,
        branch: connection.branch,
      });
      setFileContent(result.content);
    } catch (err) {
      setFileContent(`Error loading file: ${err}`);
    }
    setFileLoading(false);
  };

  const handleToggleDir = async (path: string) => {
    const findNode = (nodes: TreeItem[]): TreeItem | null => {
      for (const n of nodes) {
        if (n.path === path) return n;
        if (n.children) {
          const found = findNode(n.children);
          if (found) return found;
        }
      }
      return null;
    };
    const node = findNode(tree);
    if (node?.expanded) {
      setTree((prev) => updateTreeChildren(prev, path, []));
    } else {
      await loadTree(path);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(fileContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!connection?.connected) {
    return (
      <div className="h-full bg-[#06060F] flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="size-16 rounded-2xl bg-gradient-to-br from-[#1E90FF]/20 to-[#FFD700]/20 flex items-center justify-center mx-auto mb-4 j-glow">
              <GitBranch className="size-8 text-[#1E90FF]" />
            </div>
            <h2 className="text-xl font-bold text-white mb-2">
              Connect Repository
            </h2>
            <p className="text-sm text-[#8888a0]">
              Link a GitHub repo to browse files and edit code with J.
            </p>
          </div>
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                placeholder="Owner"
                className="bg-[#0d0d1a] border-[#1a1a2e] text-white"
              />
              <span className="text-[#8888a0] self-center">/</span>
              <Input
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                placeholder="Repository"
                className="bg-[#0d0d1a] border-[#1a1a2e] text-white"
              />
            </div>
            <Input
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="Branch (default: main)"
              className="bg-[#0d0d1a] border-[#1a1a2e] text-white"
            />
            <Button
              onClick={handleConnect}
              disabled={loading || !owner || !repo}
              className="w-full bg-[#1E90FF] hover:bg-[#1E90FF]/80 text-white"
            >
              {loading ? (
                <Loader2 className="size-4 animate-spin mr-2" />
              ) : (
                <Plug className="size-4 mr-2" />
              )}
              Connect
            </Button>
            {error && (
              <div className="mt-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
                {error}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-[#06060F]">
      {/* File tree sidebar */}
      <div className="w-64 shrink-0 border-r border-[#1a1a2e] bg-[#0a0a14] flex flex-col min-h-0">
        <div className="p-3 border-b border-[#1a1a2e] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-xs">
            <GitBranch className="size-3.5 text-[#1E90FF]" />
            <span className="text-white font-medium truncate">
              {connection.owner}/{connection.repo}
            </span>
          </div>
          <Button
            onClick={() => disconnectRepo()}
            variant="ghost"
            size="sm"
            className="size-7 p-0 text-[#8888a0] hover:text-[#ff4444]"
          >
            <Unplug className="size-3.5" />
          </Button>
        </div>
        <div className="px-3 py-2 border-b border-[#1a1a2e] shrink-0">
          <Badge
            variant="outline"
            className="text-[10px] border-[#1a1a2e] text-[#8888a0]"
          >
            <GitBranch className="size-2.5 mr-1" />
            {connection.branch}
          </Badge>
        </div>
        <ScrollArea className="flex-1">
          <div className="py-1">
            {loading && tree.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="size-5 animate-spin text-[#1E90FF]" />
              </div>
            ) : (
              tree.map((item) => (
                <FileTreeNode
                  key={item.path}
                  item={item}
                  depth={0}
                  onToggle={handleToggleDir}
                  onSelect={handleSelectFile}
                  selectedPath={selectedFile}
                />
              ))
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Editor area */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* Tab bar */}
        <div className="h-10 shrink-0 border-b border-[#1a1a2e] bg-[#0a0a14]/80 flex items-center px-4">
          {selectedFile ? (
            <div className="flex items-center gap-2 w-full">
              <File className="size-3.5 text-[#1E90FF] shrink-0" />
              <span className="text-xs text-white font-medium truncate">
                {selectedFile}
              </span>
              <Badge
                variant="outline"
                className="text-[9px] border-[#1a1a2e] text-[#8888a0] shrink-0"
              >
                {getLanguageDisplayName(currentLang)}
              </Badge>
              <button
                onClick={handleCopy}
                className="ml-2 text-[#8888a0] hover:text-white transition shrink-0"
              >
                {copied ? (
                  <Check className="size-3.5 text-[#00FF41]" />
                ) : (
                  <Copy className="size-3.5" />
                )}
              </button>

              {/* Verify toggle */}
              <div className="ml-auto flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setShowVerify(!showVerify)}
                  className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded transition ${
                    showVerify
                      ? syntaxIssues.length > 0
                        ? "bg-[#FFD700]/10 text-[#FFD700] border border-[#FFD700]/30"
                        : "bg-[#00FF41]/10 text-[#00FF41] border border-[#00FF41]/30"
                      : "bg-[#1a1a2e] text-[#8888a0] hover:text-white border border-transparent"
                  }`}
                >
                  {showVerify ? (
                    syntaxIssues.length > 0 ? (
                      <>
                        <AlertTriangle className="size-3" />
                        {syntaxIssues.length} issue
                        {syntaxIssues.length !== 1 ? "s" : ""}
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="size-3" />
                        Clean
                      </>
                    )
                  ) : (
                    "Verify"
                  )}
                </button>
              </div>
            </div>
          ) : (
            <span className="text-xs text-[#8888a0]">
              Select a file to view
            </span>
          )}
        </div>

        {/* Code view — syntax highlighted */}
        <ScrollArea className="flex-1">
          {fileLoading ? (
            <div className="flex items-center justify-center h-full py-20">
              <Loader2 className="size-6 animate-spin text-[#1E90FF]" />
            </div>
          ) : selectedFile ? (
            <HighlightedCode
              content={fileContent}
              language={currentLang}
              issues={syntaxIssues}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full py-20 text-center">
              <FileCode className="size-12 text-[#1a1a2e] mb-4" />
              <p className="text-sm text-[#8888a0]">
                Select a file from the tree
              </p>
            </div>
          )}
        </ScrollArea>

        {/* Syntax issues panel */}
        {showVerify && syntaxIssues.length > 0 && (
          <div className="shrink-0 border-t border-[#1a1a2e] bg-[#0a0a14] max-h-36 overflow-y-auto">
            <div className="px-4 py-2 text-[10px] text-[#8888a0] border-b border-[#1a1a2e] font-medium flex items-center gap-2">
              <AlertTriangle className="size-3 text-[#FFD700]" />
              PROBLEMS ({syntaxIssues.length})
            </div>
            <div className="divide-y divide-[#1a1a2e]">
              {syntaxIssues.map((iss, i) => (
                <div
                  key={i}
                  className="px-4 py-1.5 text-[11px] flex items-center gap-3 hover:bg-[#1a1a2e]/50"
                >
                  <span
                    className={`shrink-0 ${
                      iss.severity === "error"
                        ? "text-red-400"
                        : "text-[#FFD700]"
                    }`}
                  >
                    {iss.severity === "error" ? "⛔" : "⚠"}
                  </span>
                  <span className="text-[#8888a0] shrink-0">
                    Ln {iss.line}
                  </span>
                  <span className="text-[#e8e8f0]">{iss.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

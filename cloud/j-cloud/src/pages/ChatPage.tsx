import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useAction } from "convex/react";
import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Send,
  Plus,
  Trash2,
  MessageSquare,
  Bot,
  User,
  Loader2,
  Zap,
  Volume2,
  VolumeX,
  Mic,
  MicOff,
  Paperclip,
  X,
  FileText,
  Image as ImageIcon,
  FileCode,
  Menu,
  ChevronLeft,
} from "lucide-react";

// =================== VOICE: TTS + STT ===================

function useTTS() {
  const [speaking, setSpeaking] = useState(false);
  const utterRef = useRef<SpeechSynthesisUtterance | null>(null);

  const speak = useCallback((text: string) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    // Strip code blocks and markdown for cleaner speech
    const clean = text
      .replace(/```[\s\S]*?```/g, " (code block) ")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\[TOOL RESULT\][\s\S]*?(?=\n\n|\n[A-Z]|$)/g, " (tool executed) ")
      .replace(/ACTION:\{[\s\S]*?\}/g, "")
      .replace(/https?:\/\/\S+/g, " (link) ")
      .trim();

    if (!clean) return;

    const utter = new SpeechSynthesisUtterance(clean);
    // Try to find a natural English voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(
      (v) =>
        v.lang.startsWith("en") &&
        (v.name.includes("Google") ||
          v.name.includes("Samantha") ||
          v.name.includes("Daniel") ||
          v.name.includes("Natural") ||
          v.name.includes("Neural"))
    );
    if (preferred) utter.voice = preferred;
    utter.rate = 1.05;
    utter.pitch = 0.95;
    utter.onstart = () => setSpeaking(true);
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    utterRef.current = utter;
    window.speechSynthesis.speak(utter);
  }, []);

  const stop = useCallback(() => {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  return { speak, stop, speaking };
}

function useSTT(onResult: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const recogRef = useRef<any>(null);

  const start = useCallback(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recog = new SpeechRecognition();
    recog.continuous = false;
    recog.interimResults = false;
    recog.lang = "en-US";

    recog.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      onResult(transcript);
      setListening(false);
    };
    recog.onerror = () => setListening(false);
    recog.onend = () => setListening(false);

    recogRef.current = recog;
    recog.start();
    setListening(true);
  }, [onResult]);

  const stop = useCallback(() => {
    recogRef.current?.stop();
    setListening(false);
  }, []);

  return { start, stop, listening };
}

// =================== FILE ATTACH ===================

interface AttachedFile {
  name: string;
  type: string;
  size: number;
  content: string; // text content or base64 for images
  isImage: boolean;
}

async function readFileAsText(file: File): Promise<AttachedFile> {
  const isImage = file.type.startsWith("image/");
  const isText =
    file.type.startsWith("text/") ||
    file.name.match(/\.(py|ts|tsx|js|jsx|json|md|yml|yaml|toml|css|html|sh|bash|cfg|txt|rs|go|java|c|cpp|h|rb|php|sql|xml|csv|env|ini|conf|log|gitignore|dockerfile|makefile)$/i) ||
    file.type === "application/json" ||
    file.type === "application/xml" ||
    file.type === "";

  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    if (isImage) {
      reader.onload = () =>
        resolve({
          name: file.name,
          type: file.type,
          size: file.size,
          content: reader.result as string,
          isImage: true,
        });
      reader.onerror = reject;
      reader.readAsDataURL(file);
    } else if (isText) {
      reader.onload = () =>
        resolve({
          name: file.name,
          type: file.type,
          size: file.size,
          content: (reader.result as string).slice(0, 50000), // 50k char limit
          isImage: false,
        });
      reader.onerror = reject;
      reader.readAsText(file);
    } else {
      // Binary file — just note it
      resolve({
        name: file.name,
        type: file.type,
        size: file.size,
        content: `[Binary file: ${file.name} (${(file.size / 1024).toFixed(1)}KB, ${file.type || "unknown type"})]`,
        isImage: false,
      });
    }
  });
}

function FilePreview({
  file,
  onRemove,
}: {
  file: AttachedFile;
  onRemove: () => void;
}) {
  const icon = file.isImage ? (
    <ImageIcon className="size-3.5" />
  ) : file.name.match(/\.(py|ts|tsx|js|jsx|rs|go|java|c|cpp|rb|php)$/i) ? (
    <FileCode className="size-3.5" />
  ) : (
    <FileText className="size-3.5" />
  );

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0d0d1a] border border-[#1a1a2e] rounded-lg text-xs">
      <span className="text-[#1E90FF]">{icon}</span>
      <span className="text-[#e8e8f0] truncate max-w-[150px]">{file.name}</span>
      <span className="text-[#8888a0]">
        {file.size > 1024 ? `${(file.size / 1024).toFixed(1)}K` : `${file.size}B`}
      </span>
      <button
        onClick={onRemove}
        className="text-[#8888a0] hover:text-[#ff4444] transition ml-1"
      >
        <X className="size-3" />
      </button>
    </div>
  );
}

// =================== MESSAGE BUBBLE ===================

function MessageBubble({
  role,
  content,
  metadata,
  toolCalls,
  isLatest,
  onSpeak,
  onStop,
  isSpeaking,
}: {
  role: string;
  content: string;
  metadata?: { model?: string; latencyMs?: number; tokensUsed?: number };
  toolCalls?: Array<{
    tool: string;
    args: string;
    result?: string;
    status: string;
  }>;
  isLatest?: boolean;
  onSpeak?: (text: string) => void;
  onStop?: () => void;
  isSpeaking?: boolean;
}) {
  const isAssistant = role === "assistant";

  return (
    <div className={`flex gap-3 ${isAssistant ? "" : "flex-row-reverse"}`}>
      <div
        className={`shrink-0 size-8 rounded-lg flex items-center justify-center ${
          isAssistant
            ? "bg-[#1E90FF]/20 text-[#1E90FF]"
            : "bg-[#FFD700]/20 text-[#FFD700]"
        }`}
      >
        {isAssistant ? (
          <Bot className="size-4" />
        ) : (
          <User className="size-4" />
        )}
      </div>
      <div
        className={`max-w-[85%] sm:max-w-[80%] rounded-xl px-3 sm:px-4 py-2.5 sm:py-3 ${
          isAssistant
            ? "bg-[#0d0d1a] border border-[#1a1a2e]"
            : "bg-[#1E90FF]/10 border border-[#1E90FF]/20"
        }`}
      >
        {toolCalls && toolCalls.length > 0 && (
          <div className="mb-3 space-y-2">
            {toolCalls.map((tc, i) => (
              <div
                key={i}
                className="rounded-lg bg-[#0a0a15] border border-[#2a2a3a] p-2.5 text-xs"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={
                      tc.status === "success"
                        ? "text-[#00FF41]"
                        : "text-red-400"
                    }
                  >
                    {tc.status === "success" ? "✓" : "✗"}
                  </span>
                  <span className="text-[#00d4aa] font-mono font-semibold">
                    {tc.tool}
                  </span>
                </div>
                {tc.result && (
                  <pre className="text-[#8888a0] whitespace-pre-wrap break-all max-h-32 overflow-y-auto mt-1 text-[10px] leading-relaxed">
                    {tc.result.slice(0, 500)}
                    {tc.result.length > 500 ? "…" : ""}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
        <div
          className={`text-sm whitespace-pre-wrap leading-relaxed ${isLatest && isAssistant ? "j-cursor" : ""}`}
        >
          {content.startsWith("⚠️") ? (
            <span className="text-[#FFD700]">{content}</span>
          ) : (
            formatContent(content)
          )}
        </div>
        {isAssistant && (
          <div className="flex items-center gap-3 mt-2">
            {metadata && (
              <div className="flex gap-3 text-[10px] text-[#8888a0]">
                {metadata.model && <span>{metadata.model}</span>}
                {metadata.latencyMs && <span>{metadata.latencyMs}ms</span>}
              </div>
            )}
            {onSpeak && (
              <button
                onClick={() => (isSpeaking ? onStop?.() : onSpeak(content))}
                className="ml-auto text-[#8888a0] hover:text-[#1E90FF] transition"
                title={isSpeaking ? "Stop speaking" : "Read aloud"}
              >
                {isSpeaking ? (
                  <VolumeX className="size-3.5" />
                ) : (
                  <Volume2 className="size-3.5" />
                )}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function formatContent(text: string) {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts.map((part, i) => {
    if (part.startsWith("```") && part.endsWith("```")) {
      const code = part.slice(3, -3).replace(/^\w+\n/, "");
      return (
        <pre
          key={i}
          className="mt-2 mb-2 p-3 rounded-lg bg-[#06060F] border border-[#1a1a2e] overflow-x-auto font-mono text-xs text-[#00d4aa]"
        >
          {code}
        </pre>
      );
    }
    const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
    return boldParts.map((bp, j) => {
      if (bp.startsWith("**") && bp.endsWith("**")) {
        return (
          <strong key={`${i}-${j}`} className="text-[#1E90FF] font-semibold">
            {bp.slice(2, -2)}
          </strong>
        );
      }
      return <span key={`${i}-${j}`}>{bp}</span>;
    });
  });
}

// =================== CONVERSATION LIST ===================

function ConversationList({
  activeId,
  onSelect,
}: {
  activeId: Id<"conversations"> | null;
  onSelect: (id: Id<"conversations">) => void;
}) {
  const conversations = useQuery(api.conversations.list, {}) || [];
  const createConvo = useMutation(api.conversations.create);
  const deleteConvo = useMutation(api.conversations.remove);

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-[#1a1a2e]">
        <Button
          onClick={() => createConvo({}).then(onSelect)}
          className="w-full bg-[#1E90FF] hover:bg-[#1E90FF]/80 text-white"
          size="sm"
        >
          <Plus className="size-4 mr-1" /> New Chat
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {conversations.length === 0 && (
            <p className="text-xs text-[#8888a0] text-center py-4">
              No conversations yet
            </p>
          )}
          {conversations.map((c) => (
            <button
              key={c._id}
              onClick={() => onSelect(c._id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition group ${
                activeId === c._id
                  ? "bg-[#1E90FF]/15 border border-[#1E90FF]/30 text-white"
                  : "hover:bg-[#1a1a2e] text-[#8888a0] hover:text-white"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 truncate">
                  <MessageSquare className="size-3 shrink-0" />
                  <span className="truncate">{c.title}</span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConvo({ id: c._id });
                  }}
                  className="opacity-0 group-hover:opacity-100 text-[#8888a0] hover:text-[#ff4444] transition"
                >
                  <Trash2 className="size-3" />
                </button>
              </div>
              {c.lastMessage && (
                <p className="text-[10px] text-[#8888a0] truncate mt-0.5 ml-5">
                  {c.lastMessage}
                </p>
              )}
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

// =================== MAIN CHAT PAGE ===================

export function ChatPage() {
  const [activeConvo, setActiveConvo] =
    useState<Id<"conversations"> | null>(null);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const messages = useQuery(
    api.messages.list,
    activeConvo ? { conversationId: activeConvo } : "skip"
  );
  const sendMessage = useMutation(api.messages.send);
  const chatAction = useAction(api.llm.chat);
  const model = useQuery(api.admin.getSetting, { key: "default_model" });

  // Voice hooks
  const { speak, stop: stopSpeak, speaking } = useTTS();
  const onSpeechResult = useCallback(
    (transcript: string) => {
      setInput((prev) => (prev ? prev + " " + transcript : transcript));
    },
    []
  );
  const { start: startListening, stop: stopListening, listening } = useSTT(onSpeechResult);

  // Load voices (Chrome needs this)
  useEffect(() => {
    window.speechSynthesis?.getVoices();
    const onVoicesChanged = () => window.speechSynthesis?.getVoices();
    window.speechSynthesis?.addEventListener?.("voiceschanged", onVoicesChanged);
    return () =>
      window.speechSynthesis?.removeEventListener?.(
        "voiceschanged",
        onVoicesChanged
      );
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // File handling
  const handleFiles = async (files: FileList | File[]) => {
    const newFiles: AttachedFile[] = [];
    for (const file of Array.from(files)) {
      if (file.size > 5 * 1024 * 1024) {
        // 5MB limit
        alert(`File too large: ${file.name} (max 5MB)`);
        continue;
      }
      try {
        const attached = await readFileAsText(file);
        newFiles.push(attached);
      } catch (err) {
        console.error("Error reading file:", err);
      }
    }
    setAttachedFiles((prev) => [...prev, ...newFiles]);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      await handleFiles(e.dataTransfer.files);
    }
  };

  const handleSend = async () => {
    if ((!input.trim() && attachedFiles.length === 0) || !activeConvo || isLoading)
      return;

    // Build the message with file content
    let fullMessage = input.trim();
    if (attachedFiles.length > 0) {
      const fileContexts = attachedFiles.map((f) => {
        if (f.isImage) {
          return `[Attached image: ${f.name}]`;
        }
        return `[FILE: ${f.name}]\n${f.content}`;
      });
      const fileBlock = fileContexts.join("\n\n");
      fullMessage = fullMessage
        ? `${fullMessage}\n\n${fileBlock}`
        : fileBlock;
    }

    setInput("");
    setAttachedFiles([]);
    setIsLoading(true);
    try {
      await sendMessage({ conversationId: activeConvo, content: fullMessage });
      await chatAction({
        conversationId: activeConvo,
        userMessage: fullMessage,
        model: model || undefined,
      });
    } catch (err) {
      console.error("Chat error:", err);
    }
    setIsLoading(false);
  };

  const createConvo = useMutation(api.conversations.create);

  const handleMobileSelect = (id: Id<"conversations">) => {
    setActiveConvo(id);
    setMobileMenuOpen(false);
  };

  const handleMobileNewChat = async () => {
    const id = await createConvo({});
    setActiveConvo(id);
    setMobileMenuOpen(false);
  };

  return (
    <div className="flex h-full bg-[#06060F]">
      {/* Desktop sidebar — conversation list */}
      <div className="hidden md:flex w-64 border-r border-[#1a1a2e] bg-[#0a0a14] flex-col">
        <div className="p-4 border-b border-[#1a1a2e]">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-lg bg-gradient-to-br from-[#1E90FF] to-[#00d4aa] flex items-center justify-center">
              <Zap className="size-4 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-white">J Cloud</h1>
              <p className="text-[10px] text-[#8888a0]">
                Sovereign Shards Agent
              </p>
            </div>
          </div>
        </div>
        <ConversationList activeId={activeConvo} onSelect={setActiveConvo} />
      </div>

      {/* Mobile slide-over panel */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
          />
          {/* Panel */}
          <div className="relative w-72 max-w-[80vw] h-full bg-[#0a0a14] border-r border-[#1a1a2e] flex flex-col animate-in slide-in-from-left duration-200">
            <div className="p-4 border-b border-[#1a1a2e] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="size-8 rounded-lg bg-gradient-to-br from-[#1E90FF] to-[#00d4aa] flex items-center justify-center">
                  <Zap className="size-4 text-white" />
                </div>
                <div>
                  <h1 className="text-sm font-bold text-white">J Cloud</h1>
                  <p className="text-[10px] text-[#8888a0]">Conversations</p>
                </div>
              </div>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="text-[#8888a0] hover:text-white p-1"
              >
                <ChevronLeft className="size-5" />
              </button>
            </div>
            <ConversationList activeId={activeConvo} onSelect={handleMobileSelect} />
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col relative min-h-0">
        {/* Header */}
        <div className="h-12 shrink-0 border-b border-[#1a1a2e] bg-[#0a0a14]/80 backdrop-blur-sm flex items-center px-3 sm:px-4 gap-2 sm:gap-3">
          {/* Mobile menu toggle */}
          <button
            onClick={() => setMobileMenuOpen(true)}
            className="md:hidden text-[#8888a0] hover:text-white p-1 -ml-1"
          >
            <Menu className="size-5" />
          </button>

          <div className="flex items-center gap-2">
            <div className="size-2 rounded-full bg-[#00FF41] animate-pulse" />
            <span className="text-sm font-medium text-white">J</span>
            <Badge
              variant="outline"
              className="text-[10px] border-[#1a1a2e] text-[#8888a0] hidden sm:inline-flex"
            >
              {model || "gemini-2.0-flash"}
            </Badge>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <span className="text-[10px] text-[#8888a0] hidden sm:inline">4096 tokens</span>
            {speaking && (
              <Badge className="bg-[#1E90FF]/20 text-[#1E90FF] text-[9px] border-none">
                <Volume2 className="size-2.5 mr-1" /> Speaking
              </Badge>
            )}
            {/* Mobile new chat button */}
            <Button
              onClick={handleMobileNewChat}
              variant="ghost"
              size="sm"
              className="md:hidden text-[#1E90FF] hover:bg-[#1E90FF]/10 h-8 w-8 p-0"
              title="New chat"
            >
              <Plus className="size-4" />
            </Button>
          </div>
        </div>

        {/* Messages — drag & drop zone */}
        <div
          ref={scrollRef}
          className={`flex-1 overflow-y-auto p-4 space-y-4 relative j-scanlines transition-colors ${
            dragOver
              ? "bg-[#1E90FF]/5 ring-2 ring-inset ring-[#1E90FF]/30"
              : ""
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          {dragOver && (
            <div className="absolute inset-0 flex items-center justify-center z-10 bg-[#06060F]/80 backdrop-blur-sm">
              <div className="text-center">
                <Paperclip className="size-10 text-[#1E90FF] mx-auto mb-2" />
                <p className="text-sm text-[#1E90FF] font-medium">
                  Drop files here
                </p>
                <p className="text-xs text-[#8888a0]">
                  Code, text, images — up to 5MB
                </p>
              </div>
            </div>
          )}

          {!activeConvo ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <div className="size-16 rounded-2xl bg-gradient-to-br from-[#1E90FF]/20 to-[#00d4aa]/20 flex items-center justify-center mb-4 j-glow">
                <Bot className="size-8 text-[#1E90FF]" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Talk to J</h2>
              <p className="text-sm text-[#8888a0] max-w-sm mb-4">
                Start a new conversation or select an existing one.
                <br />
                J plans, codes, tests, and ships — autonomously.
              </p>
              {/* Mobile-visible new chat button */}
              <Button
                onClick={handleMobileNewChat}
                className="bg-[#1E90FF] hover:bg-[#1E90FF]/80 text-white px-6 py-2.5 text-sm"
              >
                <Plus className="size-4 mr-2" /> New Chat
              </Button>
            </div>
          ) : messages?.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="size-12 rounded-xl bg-[#1E90FF]/10 flex items-center justify-center mb-3">
                <Bot className="size-6 text-[#1E90FF]" />
              </div>
              <p className="text-sm text-[#8888a0]">
                What do you need, architect?
              </p>
            </div>
          ) : (
            messages?.map((msg, i) => (
              <MessageBubble
                key={msg._id}
                role={msg.role}
                content={msg.content}
                metadata={msg.metadata}
                toolCalls={msg.toolCalls}
                isLatest={
                  i === (messages?.length ?? 0) - 1 &&
                  msg.role === "assistant"
                }
                onSpeak={msg.role === "assistant" ? speak : undefined}
                onStop={stopSpeak}
                isSpeaking={speaking}
              />
            ))
          )}
          {isLoading && (
            <div className="flex gap-3">
              <div className="size-8 rounded-lg bg-[#1E90FF]/20 flex items-center justify-center">
                <Bot className="size-4 text-[#1E90FF]" />
              </div>
              <div className="bg-[#0d0d1a] border border-[#1a1a2e] rounded-xl px-4 py-3">
                <div className="flex items-center gap-2 text-sm text-[#8888a0]">
                  <Loader2 className="size-4 animate-spin text-[#1E90FF]" />
                  <span>J is thinking…</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Attached files preview */}
        {attachedFiles.length > 0 && (
          <div className="px-4 py-2 border-t border-[#1a1a2e] bg-[#0a0a14]/50 flex flex-wrap gap-2">
            {attachedFiles.map((f, i) => (
              <FilePreview
                key={`${f.name}-${i}`}
                file={f}
                onRemove={() =>
                  setAttachedFiles((prev) => prev.filter((_, j) => j !== i))
                }
              />
            ))}
          </div>
        )}

        {/* Input */}
        <div className="border-t border-[#1a1a2e] bg-[#0a0a14]/80 backdrop-blur-sm p-2 sm:p-4 shrink-0">
          <div className="flex gap-1.5 sm:gap-2 items-end">
            {/* File attach button */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files) handleFiles(e.target.files);
                e.target.value = "";
              }}
            />
            <Button
              onClick={() => fileInputRef.current?.click()}
              disabled={!activeConvo}
              variant="ghost"
              size="sm"
              className="shrink-0 text-[#8888a0] hover:text-[#1E90FF] hover:bg-[#1E90FF]/10 size-9 sm:size-10 p-0"
              title="Attach files"
            >
              <Paperclip className="size-4" />
            </Button>

            {/* Mic button — hidden on very small screens to save space */}
            <Button
              onClick={() => (listening ? stopListening() : startListening())}
              disabled={!activeConvo}
              variant="ghost"
              size="sm"
              className={`shrink-0 hidden xs:flex size-9 sm:size-10 p-0 ${
                listening
                  ? "text-[#ff4444] bg-[#ff4444]/10 hover:bg-[#ff4444]/20 hover:text-[#ff4444]"
                  : "text-[#8888a0] hover:text-[#1E90FF] hover:bg-[#1E90FF]/10"
              }`}
              title={listening ? "Stop listening" : "Voice input"}
            >
              {listening ? (
                <MicOff className="size-4" />
              ) : (
                <Mic className="size-4" />
              )}
            </Button>

            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={
                listening
                  ? "Listening…"
                  : activeConvo
                    ? "Message J…"
                    : "Start a new chat →"
              }
              disabled={!activeConvo || isLoading}
              className={`flex-1 min-w-0 bg-[#0d0d1a] border rounded-xl px-3 sm:px-4 py-2.5 text-sm text-white placeholder:text-[#8888a0] focus:outline-none focus:border-[#1E90FF]/50 focus:ring-1 focus:ring-[#1E90FF]/20 transition disabled:opacity-50 ${
                listening
                  ? "border-[#ff4444]/50 animate-pulse"
                  : "border-[#1a1a2e]"
              }`}
            />
            <Button
              onClick={handleSend}
              disabled={
                !activeConvo ||
                (!input.trim() && attachedFiles.length === 0) ||
                isLoading
              }
              className="bg-[#1E90FF] hover:bg-[#1E90FF]/80 text-white shrink-0 size-10 sm:px-4 sm:w-auto p-0 sm:p-2"
            >
              <Send className="size-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

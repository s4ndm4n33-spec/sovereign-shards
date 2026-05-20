import { useConvexAuth, useAction, useMutation, useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";
import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  Hash,
  Send,
  Code,
  Image,
  SmilePlus,
  Shield,
  Menu,
  X,
  AlertTriangle,
  ChevronDown,
  LogIn,
  UserPlus,
  Bot,
  Cpu,
} from "lucide-react";

const EMOJI_LIST = ["👍", "👎", "🔥", "💡", "🚀", "⚡", "🛡️", "💀", "👀", "✅", "❌", "🤔"];

function getAnonymousId(): string {
  let id = localStorage.getItem("ss-anon-id");
  if (!id) {
    id = "ghost-" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem("ss-anon-id", id);
  }
  return id;
}

function getAnonymousName(): string {
  let name = localStorage.getItem("ss-anon-name");
  if (!name) {
    const adjectives = ["Silent", "Shadow", "Phantom", "Rogue", "Void", "Cipher", "Drift", "Echo", "Null", "Arc"];
    const nouns = ["Node", "Shard", "Core", "Agent", "Proxy", "Ghost", "Wire", "Pulse", "Vector", "Daemon"];
    name = adjectives[Math.floor(Math.random() * adjectives.length)] +
           nouns[Math.floor(Math.random() * nouns.length)] +
           Math.floor(Math.random() * 100);
    localStorage.setItem("ss-anon-name", name);
  }
  return name;
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDate(ts: number): string {
  const d = new Date(ts);
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return "Today";
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

// Simple markdown-ish rendering
function renderContent(content: string, messageType: string, codeLanguage?: string) {
  if (messageType === "code") {
    return (
      <pre className="bg-shard-obsidian border border-shard-violet/10 rounded-md p-3 overflow-x-auto text-sm font-mono">
        {codeLanguage && (
          <div className="text-shard-cyan text-xs mb-2 uppercase tracking-wider">{codeLanguage}</div>
        )}
        <code className="text-shard-white">{content}</code>
      </pre>
    );
  }

  if (messageType === "image") {
    return (
      <div className="max-w-md">
        <img
          src={content}
          alt="shared image"
          className="rounded-md border border-shard-violet/10 max-h-80 object-contain"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      </div>
    );
  }

  // Text with basic markdown
  const parts = content.split(/(```[\s\S]*?```|`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return (
    <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">
      {parts.map((part, i) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const code = part.slice(3, -3);
          const firstLine = code.indexOf("\n");
          const lang = firstLine > 0 ? code.slice(0, firstLine).trim() : "";
          const body = firstLine > 0 ? code.slice(firstLine + 1) : code;
          return (
            <pre key={i} className="bg-shard-obsidian border border-shard-violet/10 rounded-md p-3 my-2 overflow-x-auto font-mono text-xs">
              {lang && <div className="text-shard-cyan text-xs mb-1 uppercase tracking-wider">{lang}</div>}
              <code className="text-shard-white">{body}</code>
            </pre>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code key={i} className="bg-shard-violet/10 text-shard-cyan px-1.5 py-0.5 rounded text-xs font-mono">
              {part.slice(1, -1)}
            </code>
          );
        }
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i} className="font-semibold text-shard-white">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("*") && part.endsWith("*") && !part.startsWith("**")) {
          return <em key={i} className="italic text-shard-white/80">{part.slice(1, -1)}</em>;
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}

// Message component
function MessageBubble({
  msg,
  onReact,
  onAppeal,
}: {
  msg: NonNullable<ReturnType<typeof useQuery<typeof api.messages.list>>>[number];
  onReact: (messageId: Id<"messages">, emoji: string) => void;
  onAppeal: (messageId: Id<"messages">) => void;
}) {
  const [showEmoji, setShowEmoji] = useState(false);
  const displayName = msg.profile?.displayName ?? msg.anonymousName ?? "Ghost";
  const avatarColor = msg.profile?.avatarColor ?? "#7D8597";
  const role = msg.profile?.role;
  const initial = displayName[0]?.toUpperCase() ?? "?";

  if (msg.isDeleted) {
    return (
      <div className="px-4 py-1 opacity-40">
        <span className="text-xs text-shard-gray italic font-mono">[message deleted]</span>
      </div>
    );
  }

  if (msg.isModerated) {
    return (
      <div className="px-4 py-2 group">
        <div className="flex items-start gap-3">
          <div
            className="w-8 h-8 rounded-md flex items-center justify-center text-xs font-bold shrink-0 opacity-50"
            style={{ backgroundColor: `${avatarColor}20`, color: avatarColor }}
          >
            {initial}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-medium text-shard-gray/60">{displayName}</span>
              <span className="text-xs text-shard-gray/30 font-mono">{formatTime(msg._creationTime)}</span>
            </div>
            <div className="bg-shard-red/5 border border-shard-red/20 rounded-md p-3">
              <div className="flex items-center gap-2 text-shard-red text-xs font-mono mb-1">
                <AlertTriangle className="w-3 h-3" />
                CONTENT FILTERED
              </div>
              <p className="text-shard-gray text-xs">{msg.moderationReason}</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onAppeal(msg._id)}
                className="mt-2 text-xs text-shard-violet hover:text-shard-violet/80 h-auto py-1 px-2"
              >
                <Shield className="w-3 h-3 mr-1" />
                Appeal
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-1.5 group hover:bg-shard-violet/[0.02] transition-colors">
      <div className="flex items-start gap-3">
        <div
          className="w-8 h-8 rounded-md flex items-center justify-center text-xs font-bold shrink-0"
          style={{ backgroundColor: `${avatarColor}20`, color: avatarColor }}
        >
          {initial}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-sm font-medium text-shard-white">{displayName}</span>
            {role === "admin" && (
              <span className="px-1.5 py-0.5 bg-shard-violet/20 text-shard-violet text-[10px] font-mono rounded uppercase tracking-wider">
                ADMIN
              </span>
            )}
            {role === "moderator" && (
              <span className="px-1.5 py-0.5 bg-shard-cyan/20 text-shard-cyan text-[10px] font-mono rounded uppercase tracking-wider">
                MOD
              </span>
            )}
            {!msg.userId && (
              <span className="px-1.5 py-0.5 bg-shard-gray/10 text-shard-gray text-[10px] font-mono rounded uppercase tracking-wider">
                GUEST
              </span>
            )}
            <span className="text-xs text-shard-gray/40 font-mono">{formatTime(msg._creationTime)}</span>
          </div>

          {renderContent(msg.content, msg.messageType, msg.codeLanguage)}

          {/* Reactions */}
          <div className="flex items-center gap-1 mt-1 flex-wrap">
            {msg.reactions.map((r) => (
              <button
                key={r.emoji}
                onClick={() => onReact(msg._id, r.emoji)}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-shard-violet/10 bg-shard-violet/5 hover:bg-shard-violet/10 text-xs transition-colors"
              >
                <span>{r.emoji}</span>
                <span className="text-shard-gray font-mono">{r.count}</span>
              </button>
            ))}

            {/* Add reaction button */}
            <div className="relative">
              <button
                onClick={() => setShowEmoji(!showEmoji)}
                className="opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center justify-center w-6 h-6 rounded-full hover:bg-shard-violet/10 text-shard-gray hover:text-shard-violet"
              >
                <SmilePlus className="w-3.5 h-3.5" />
              </button>
              {showEmoji && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowEmoji(false)} />
                  <div className="absolute bottom-full left-0 mb-1 z-50 bg-shard-elevated border border-shard-violet/20 rounded-lg p-2 grid grid-cols-6 gap-1 shadow-xl">
                    {EMOJI_LIST.map((emoji) => (
                      <button
                        key={emoji}
                        onClick={() => {
                          onReact(msg._id, emoji);
                          setShowEmoji(false);
                        }}
                        className="w-8 h-8 flex items-center justify-center rounded hover:bg-shard-violet/10 text-base transition-colors"
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Message input component
function MessageInput({
  roomId,
  anonymousId,
  anonymousName,
}: {
  roomId: Id<"rooms">;
  anonymousId: string;
  anonymousName: string;
}) {
  const sendMessage = useMutation(api.messages.send);
  const [content, setContent] = useState("");
  const [messageType, setMessageType] = useState<"text" | "code" | "image">("text");
  const [codeLanguage, setCodeLanguage] = useState("");
  const [sending, setSending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(async () => {
    const trimmed = content.trim();
    if (!trimmed || sending) return;

    setSending(true);
    try {
      const result = await sendMessage({
        roomId,
        content: trimmed,
        messageType,
        codeLanguage: messageType === "code" ? codeLanguage : undefined,
        anonymousName,
        anonymousId,
      });

      if (result.moderated) {
        toast.warning("Message flagged by content filter. You may appeal.", {
          description: result.reason,
        });
      }

      setContent("");
      setMessageType("text");
      setCodeLanguage("");
    } catch {
      toast.error("Failed to send message.");
    } finally {
      setSending(false);
    }
  }, [content, sending, roomId, messageType, codeLanguage, anonymousName, anonymousId, sendMessage]);

  if (messageType === "code") {
    return (
      <div className="border-t border-shard-violet/10 bg-shard-surface p-3">
        <div className="flex items-center gap-2 mb-2">
          <Code className="w-4 h-4 text-shard-cyan" />
          <span className="text-xs font-mono text-shard-cyan">CODE BLOCK</span>
          <Input
            placeholder="language (optional)"
            value={codeLanguage}
            onChange={(e) => setCodeLanguage(e.target.value)}
            className="h-7 w-32 text-xs bg-shard-obsidian border-shard-violet/20 font-mono"
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMessageType("text")}
            className="ml-auto text-shard-gray hover:text-shard-white h-7 text-xs"
          >
            <X className="w-3 h-3" />
          </Button>
        </div>
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              handleSend();
            }
          }}
          placeholder="Paste your code here..."
          className="w-full h-32 bg-shard-obsidian border border-shard-violet/10 rounded-md p-3 text-sm font-mono text-shard-white placeholder:text-shard-gray/30 resize-none focus:outline-none focus:border-shard-violet/30"
          autoFocus
        />
        <div className="flex justify-between items-center mt-2">
          <span className="text-xs text-shard-gray/40 font-mono">⌘+Enter to send</span>
          <Button
            onClick={handleSend}
            disabled={!content.trim() || sending}
            className="bg-shard-violet hover:bg-shard-violet/80 text-white font-mono text-xs h-8"
          >
            <Send className="w-3 h-3 mr-1" />
            TRANSMIT
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="border-t border-shard-violet/10 bg-shard-surface p-3">
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setMessageType("code")}
            className="p-2 rounded-md text-shard-gray hover:text-shard-cyan hover:bg-shard-cyan/5 transition-colors"
            title="Code block"
          >
            <Code className="w-4 h-4" />
          </button>
          <button
            onClick={() => setMessageType("image")}
            className="p-2 rounded-md text-shard-gray hover:text-shard-cyan hover:bg-shard-cyan/5 transition-colors"
            title="Share image URL"
          >
            <Image className="w-4 h-4" />
          </button>
        </div>
        <input
          ref={inputRef}
          type="text"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={messageType === "image" ? "Paste image URL..." : "Transmit message..."}
          className="flex-1 h-10 bg-shard-obsidian border border-shard-violet/10 rounded-md px-3 text-sm text-shard-white placeholder:text-shard-gray/30 focus:outline-none focus:border-shard-violet/30 font-sans"
          autoFocus
        />
        <Button
          onClick={handleSend}
          disabled={!content.trim() || sending}
          size="sm"
          className="bg-shard-violet hover:bg-shard-violet/80 text-white h-10 w-10 p-0"
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>
      {messageType === "image" && (
        <div className="flex items-center gap-2 mt-2">
          <Image className="w-3 h-3 text-shard-cyan" />
          <span className="text-xs font-mono text-shard-cyan">IMAGE URL MODE</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMessageType("text")}
            className="text-shard-gray hover:text-shard-white h-5 text-xs ml-auto"
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}

export function ChatPage() {
  const { isAuthenticated } = useConvexAuth();
  const { roomId: roomIdParam } = useParams();
  const navigate = useNavigate();
  const rooms = useQuery(api.rooms.list);
  const seedRooms = useMutation(api.rooms.seed);
  const ensureProfile = useMutation(api.profiles.ensureProfile);
  const toggleReaction = useMutation(api.reactions.toggle);
  const submitAppeal = useMutation(api.appeals.submit);
  const publicAgents = useQuery(api.agents.listPublic);
  const invokeAgent = useAction(api.agents.invoke);
  const sendMessage = useMutation(api.messages.send);

  const [selectedRoom, setSelectedRoom] = useState<Id<"rooms"> | null>(null);
  const [showMobileRooms, setShowMobileRooms] = useState(false);
  const [showAgents, setShowAgents] = useState(false);
  const [anonymousId] = useState(getAnonymousId);
  const [anonymousName] = useState(getAnonymousName);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageContainerRef = useRef<HTMLDivElement>(null);
  const [isNearBottom, setIsNearBottom] = useState(true);

  // Agent invocation handler
  const handleAgentInvoke = useCallback(
    async (agentHandle: string, prompt: string) => {
      if (!selectedRoom) return;
      // Post user's agent call as a message
      await sendMessage({
        roomId: selectedRoom,
        content: `@${agentHandle} ${prompt}`,
        messageType: "text",
        anonymousName,
        anonymousId,
      });
      // Invoke the agent
      try {
        const result = await invokeAgent({
          agentHandle,
          prompt,
          roomId: selectedRoom,
        });
        if (result.success && result.response) {
          await sendMessage({
            roomId: selectedRoom,
            content: `**🤖 ${agentHandle}:** ${result.response}`,
            messageType: "text",
            anonymousName: `🤖 ${agentHandle}`,
            anonymousId: `agent-${agentHandle}`,
          });
        } else {
          toast.error(result.error ?? "Agent failed to respond.");
        }
      } catch {
        toast.error("Failed to reach agent.");
      }
    },
    [selectedRoom, sendMessage, invokeAgent, anonymousName, anonymousId],
  );

  const messages = useQuery(
    api.messages.list,
    selectedRoom ? { roomId: selectedRoom, limit: 100 } : "skip",
  );

  // Seed rooms on first load
  useEffect(() => {
    if (rooms && rooms.length === 0) {
      seedRooms();
    }
  }, [rooms, seedRooms]);

  // Ensure profile for authenticated users
  useEffect(() => {
    if (isAuthenticated) {
      ensureProfile();
    }
  }, [isAuthenticated, ensureProfile]);

  // Select first room or room from URL
  useEffect(() => {
    if (rooms && rooms.length > 0 && !selectedRoom) {
      if (roomIdParam) {
        const room = rooms.find((r) => r._id === roomIdParam);
        if (room) {
          setSelectedRoom(room._id);
          return;
        }
      }
      const defaultRoom = rooms.find((r) => r.isDefault) ?? rooms[0];
      setSelectedRoom(defaultRoom._id);
    }
  }, [rooms, selectedRoom, roomIdParam]);

  // Track scroll position
  const handleScroll = useCallback(() => {
    const container = messageContainerRef.current;
    if (!container) return;
    const { scrollTop, scrollHeight, clientHeight } = container;
    setIsNearBottom(scrollHeight - scrollTop - clientHeight < 100);
  }, []);

  // Auto-scroll to bottom on new messages if near bottom
  useEffect(() => {
    if (isNearBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isNearBottom]);

  const handleReact = useCallback(
    (messageId: Id<"messages">, emoji: string) => {
      toggleReaction({ messageId, emoji, anonymousId });
    },
    [toggleReaction, anonymousId],
  );

  const handleAppeal = useCallback(
    async (messageId: Id<"messages">) => {
      const reason = prompt("Describe why this content should be restored:");
      if (!reason) return;
      const result = await submitAppeal({ messageId, reason, anonymousId });
      if (result.success) {
        toast.success("Appeal submitted. An admin will review.");
      } else {
        toast.error(result.error ?? "Failed to submit appeal.");
      }
    },
    [submitAppeal, anonymousId],
  );

  const selectedRoomData = rooms?.find((r) => r._id === selectedRoom);

  // Group messages by date
  const groupedMessages: Array<{ date: string; messages: NonNullable<typeof messages> }> = [];
  if (messages) {
    let currentDate = "";
    for (const msg of messages) {
      const date = formatDate(msg._creationTime);
      if (date !== currentDate) {
        currentDate = date;
        groupedMessages.push({ date, messages: [msg] });
      } else {
        groupedMessages[groupedMessages.length - 1].messages.push(msg);
      }
    }
  }

  return (
    <div className="h-screen flex bg-background">
      {/* Room sidebar - desktop */}
      <aside className="hidden md:flex w-60 flex-col bg-shard-surface border-r border-shard-violet/10">
        {/* Logo */}
        <div className="px-4 py-3 border-b border-shard-violet/10">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-shard-violet/20 border border-shard-violet/30 rounded-md flex items-center justify-center">
              <span className="text-shard-violet font-mono text-xs font-bold">◈</span>
            </div>
            <div>
              <div className="text-sm font-semibold text-shard-white tracking-tight leading-none">SOVEREIGN SHARDS</div>
              <div className="text-[10px] text-shard-gray font-mono tracking-wider mt-0.5">COMMS v1.0</div>
            </div>
          </div>
        </div>

        {/* Rooms */}
        <div className="flex-1 overflow-y-auto py-2">
          <div className="px-3 mb-2">
            <span className="text-[10px] font-mono text-shard-gray/50 tracking-wider uppercase">Channels</span>
          </div>
          {rooms?.map((room) => (
            <button
              key={room._id}
              onClick={() => {
                setSelectedRoom(room._id);
                navigate(`/chat/${room._id}`, { replace: true });
              }}
              className={`w-full text-left px-3 py-2 flex items-center gap-2 transition-colors ${
                selectedRoom === room._id
                  ? "bg-shard-violet/10 text-shard-white border-r-2 border-shard-violet"
                  : "text-shard-gray hover:text-shard-white hover:bg-shard-violet/5"
              }`}
            >
              <span className="text-xs font-mono opacity-60">{room.icon}</span>
              <span className="text-sm">{room.name}</span>
            </button>
          ))}
        </div>

        {/* User area */}
        <div className="border-t border-shard-violet/10 p-3">
          {isAuthenticated ? (
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-md bg-shard-green/20 flex items-center justify-center">
                <span className="text-shard-green text-xs">●</span>
              </div>
              <div className="text-xs">
                <div className="text-shard-white font-medium">Connected</div>
                <button
                  onClick={() => navigate("/profile/setup")}
                  className="text-shard-gray hover:text-shard-violet text-[10px] font-mono"
                >
                  EDIT PROFILE
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-md bg-shard-amber/20 flex items-center justify-center">
                  <span className="text-shard-amber text-xs">◌</span>
                </div>
                <div>
                  <div className="text-xs text-shard-white">{anonymousName}</div>
                  <div className="text-[10px] text-shard-gray font-mono">GUEST</div>
                </div>
              </div>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate("/login")}
                  className="flex-1 h-7 text-[10px] font-mono text-shard-gray hover:text-shard-white"
                >
                  <LogIn className="w-3 h-3 mr-1" />
                  SIGN IN
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate("/signup")}
                  className="flex-1 h-7 text-[10px] font-mono text-shard-violet hover:text-shard-violet/80"
                >
                  <UserPlus className="w-3 h-3 mr-1" />
                  REGISTER
                </Button>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Mobile room sidebar overlay */}
      {showMobileRooms && (
        <>
          <div className="fixed inset-0 bg-black/60 z-40 md:hidden" onClick={() => setShowMobileRooms(false)} />
          <aside className="fixed left-0 top-0 bottom-0 w-64 bg-shard-surface border-r border-shard-violet/10 z-50 md:hidden">
            <div className="px-4 py-3 border-b border-shard-violet/10 flex items-center justify-between">
              <span className="text-sm font-semibold text-shard-white">CHANNELS</span>
              <button onClick={() => setShowMobileRooms(false)} className="text-shard-gray hover:text-shard-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="py-2">
              {rooms?.map((room) => (
                <button
                  key={room._id}
                  onClick={() => {
                    setSelectedRoom(room._id);
                    setShowMobileRooms(false);
                    navigate(`/chat/${room._id}`, { replace: true });
                  }}
                  className={`w-full text-left px-4 py-2.5 flex items-center gap-2 ${
                    selectedRoom === room._id
                      ? "bg-shard-violet/10 text-shard-white"
                      : "text-shard-gray hover:text-shard-white"
                  }`}
                >
                  <span className="font-mono text-xs opacity-60">{room.icon}</span>
                  <span className="text-sm">{room.name}</span>
                </button>
              ))}
            </div>
          </aside>
        </>
      )}

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Room header */}
        <header className="h-12 border-b border-shard-violet/10 bg-shard-surface flex items-center px-4 gap-3 shrink-0">
          <button
            onClick={() => setShowMobileRooms(true)}
            className="md:hidden text-shard-gray hover:text-shard-white"
          >
            <Menu className="w-5 h-5" />
          </button>
          {selectedRoomData && (
            <>
              <Hash className="w-4 h-4 text-shard-violet" />
              <span className="font-semibold text-shard-white text-sm">{selectedRoomData.name}</span>
              <span className="text-xs text-shard-gray hidden sm:inline flex-1">{selectedRoomData.description}</span>
            </>
          )}
          <button
            onClick={() => setShowAgents(!showAgents)}
            className={`ml-auto flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-mono transition-colors ${
              showAgents
                ? "bg-shard-cyan/10 text-shard-cyan"
                : "text-shard-gray hover:text-shard-cyan hover:bg-shard-cyan/5"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">AGENTS</span>
            {publicAgents && publicAgents.length > 0 && (
              <span className="bg-shard-cyan/20 text-shard-cyan px-1.5 py-0.5 rounded-full text-[10px]">
                {publicAgents.length}
              </span>
            )}
          </button>
        </header>

        {/* Messages */}
        <div
          ref={messageContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto"
        >
          {/* Welcome message */}
          {messages && messages.length === 0 && selectedRoomData && (
            <div className="flex flex-col items-center justify-center py-20 px-4 text-center">
              <div className="w-16 h-16 bg-shard-violet/10 border border-shard-violet/20 rounded-xl flex items-center justify-center mb-4">
                <span className="text-shard-violet text-2xl font-mono">{selectedRoomData.icon}</span>
              </div>
              <h2 className="text-xl font-bold text-shard-white mb-2">#{selectedRoomData.name}</h2>
              <p className="text-shard-gray text-sm max-w-md">{selectedRoomData.description}</p>
              <p className="text-shard-gray/40 text-xs font-mono mt-4">First message initializes the channel.</p>
            </div>
          )}

          {groupedMessages.map((group) => (
            <div key={group.date}>
              {/* Date separator */}
              <div className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 h-px bg-shard-violet/10" />
                <span className="text-xs font-mono text-shard-gray/40">{group.date}</span>
                <div className="flex-1 h-px bg-shard-violet/10" />
              </div>
              {group.messages.map((msg) => (
                <MessageBubble
                  key={msg._id}
                  msg={msg}
                  onReact={handleReact}
                  onAppeal={handleAppeal}
                />
              ))}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Agents panel */}
        {showAgents && (
          <div className="absolute right-0 top-12 bottom-0 w-72 bg-shard-surface border-l border-shard-violet/10 z-20 overflow-y-auto">
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-mono text-shard-cyan tracking-wider">AGENT REGISTRY</span>
                <button onClick={() => setShowAgents(false)} className="text-shard-gray hover:text-shard-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              {publicAgents?.length === 0 && (
                <div className="text-center py-8">
                  <Bot className="w-8 h-8 text-shard-gray/30 mx-auto mb-2" />
                  <p className="text-xs text-shard-gray">No agents registered yet.</p>
                  {isAuthenticated && (
                    <button
                      onClick={() => navigate("/profile/setup")}
                      className="text-xs text-shard-violet mt-2 hover:underline"
                    >
                      Register your agent →
                    </button>
                  )}
                </div>
              )}
              {publicAgents?.map((agent) => (
                <div key={agent._id} className="mb-3 bg-shard-obsidian border border-shard-violet/10 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-6 h-6 bg-shard-cyan/10 rounded flex items-center justify-center">
                      <Bot className="w-3.5 h-3.5 text-shard-cyan" />
                    </div>
                    <span className="text-sm font-medium text-shard-white">{agent.name}</span>
                  </div>
                  <div className="text-[10px] font-mono text-shard-cyan mb-1">@{agent.handle}</div>
                  <p className="text-xs text-shard-gray mb-2 line-clamp-2">{agent.description}</p>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-shard-gray/50 font-mono">
                      {agent.totalInvocations} calls • by {agent.ownerName ?? "unknown"}
                    </span>
                  </div>
                  {selectedRoom && (
                    <button
                      onClick={() => {
                        const prompt = window.prompt(`Send to @${agent.handle}:`);
                        if (prompt) handleAgentInvoke(agent.handle, prompt);
                      }}
                      className="mt-2 w-full text-xs font-mono bg-shard-cyan/10 text-shard-cyan hover:bg-shard-cyan/20 rounded px-2 py-1.5 transition-colors"
                    >
                      INVOKE →
                    </button>
                  )}
                </div>
              ))}
              {isAuthenticated && (
                <button
                  onClick={() => navigate("/profile/setup")}
                  className="w-full mt-2 text-xs font-mono border border-dashed border-shard-violet/20 text-shard-gray hover:text-shard-violet hover:border-shard-violet/40 rounded-lg p-3 transition-colors"
                >
                  + Register Your Agent
                </button>
              )}
            </div>
          </div>
        )}

        {/* Scroll to bottom indicator */}
        {!isNearBottom && (
          <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-30">
            <button
              onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })}
              className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-shard-violet text-white text-xs font-mono shadow-lg"
            >
              <ChevronDown className="w-3 h-3" />
              New messages
            </button>
          </div>
        )}

        {/* Message input */}
        {selectedRoom && (
          <MessageInput
            roomId={selectedRoom}
            anonymousId={anonymousId}
            anonymousName={anonymousName}
          />
        )}
      </main>
    </div>
  );
}

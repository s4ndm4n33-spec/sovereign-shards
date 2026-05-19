import { useQuery, useMutation } from "convex/react";
import { api } from "../../convex/_generated/api";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Link2,
  Trash2,
  Activity,
  CheckCircle2,
  XCircle,
  PauseCircle,
  Loader2,
  ChevronRight,
  Zap,
} from "lucide-react";

const STATUS_CONFIG = {
  running: { icon: Loader2, color: "text-[#1E90FF]", bg: "bg-[#1E90FF]/15", label: "Running", animate: true },
  done: { icon: CheckCircle2, color: "text-[#00FF41]", bg: "bg-[#00FF41]/15", label: "Complete", animate: false },
  error: { icon: XCircle, color: "text-[#ff4444]", bg: "bg-[#ff4444]/15", label: "Error", animate: false },
  paused: { icon: PauseCircle, color: "text-[#FFD700]", bg: "bg-[#FFD700]/15", label: "Paused", animate: false },
};

export function ChainLogsPage() {
  const sessions = useQuery(api.chainLogs.sessions) || [];
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const logs = useQuery(
    api.chainLogs.list,
    selectedSession ? { sessionId: selectedSession } : "skip"
  );
  const clearSession = useMutation(api.chainLogs.clearSession);

  return (
    <div className="flex h-[calc(100vh-3rem)] md:h-screen bg-[#06060F]">
      {/* Sessions sidebar */}
      <div className="w-72 border-r border-[#1a1a2e] bg-[#0a0a14] flex flex-col">
        <div className="p-4 border-b border-[#1a1a2e]">
          <div className="flex items-center gap-2">
            <Link2 className="size-4 text-[#1E90FF]" />
            <h2 className="text-sm font-bold text-white">Chain Sessions</h2>
          </div>
          <p className="text-[10px] text-[#8888a0] mt-1">
            J's checkpoint/resume execution chains
          </p>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {sessions.length === 0 ? (
              <div className="text-center py-8">
                <Activity className="size-8 text-[#1a1a2e] mx-auto mb-2" />
                <p className="text-xs text-[#8888a0]">No chain sessions yet</p>
                <p className="text-[10px] text-[#8888a0]/60 mt-1">
                  Chains appear when J runs multi-step tasks
                </p>
              </div>
            ) : (
              sessions.map((session) => {
                const cfg = STATUS_CONFIG[session.status];
                const StatusIcon = cfg.icon;
                return (
                  <button
                    key={session.sessionId}
                    onClick={() => setSelectedSession(session.sessionId)}
                    className={`w-full text-left px-3 py-2.5 rounded-lg transition group ${
                      selectedSession === session.sessionId
                        ? "bg-[#1E90FF]/15 border border-[#1E90FF]/30"
                        : "hover:bg-[#1a1a2e]"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-white truncate">
                        {session.sessionId.slice(0, 20)}…
                      </span>
                      <Badge className={`text-[9px] ${cfg.bg} ${cfg.color} border-0`}>
                        <StatusIcon className={`size-2.5 mr-0.5 ${cfg.animate ? "animate-spin" : ""}`} />
                        {cfg.label}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-[#8888a0]">
                      <span>Phase: {session.phase}</span>
                      <span>{session.steps} steps</span>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-[10px] text-[#8888a0]/60">
                        {new Date(session.lastActivity).toLocaleDateString()}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          clearSession({ sessionId: session.sessionId });
                          if (selectedSession === session.sessionId) setSelectedSession(null);
                        }}
                        className="opacity-0 group-hover:opacity-100 text-[#8888a0] hover:text-[#ff4444] transition"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Chain detail view */}
      <div className="flex-1 flex flex-col">
        <div className="h-12 border-b border-[#1a1a2e] bg-[#0a0a14]/80 flex items-center px-4">
          {selectedSession ? (
            <div className="flex items-center gap-2 text-sm">
              <Zap className="size-4 text-[#FFD700]" />
              <span className="text-white font-medium">Session: {selectedSession.slice(0, 30)}…</span>
              <span className="text-[#8888a0]">•</span>
              <span className="text-[#8888a0]">{logs?.length || 0} steps</span>
            </div>
          ) : (
            <span className="text-xs text-[#8888a0]">Select a session to view chain details</span>
          )}
        </div>

        <ScrollArea className="flex-1">
          {!selectedSession ? (
            <div className="flex flex-col items-center justify-center h-full py-20">
              <Link2 className="size-12 text-[#1a1a2e] mb-4" />
              <p className="text-sm text-[#8888a0]">Select a chain session</p>
            </div>
          ) : (
            <div className="p-6 space-y-2">
              {logs?.map((log, i) => {
                const cfg = STATUS_CONFIG[log.status];
                const StatusIcon = cfg.icon;
                return (
                  <div
                    key={log._id}
                    className="border border-[#1a1a2e] rounded-lg bg-[#0a0a14] overflow-hidden"
                  >
                    <div className="flex items-center gap-3 px-4 py-3">
                      {/* Step connector */}
                      <div className="flex flex-col items-center">
                        <div className={`size-6 rounded-full ${cfg.bg} flex items-center justify-center`}>
                          <StatusIcon className={`size-3 ${cfg.color} ${cfg.animate ? "animate-spin" : ""}`} />
                        </div>
                        {i < (logs?.length || 0) - 1 && (
                          <div className="w-px h-4 bg-[#1a1a2e] mt-1" />
                        )}
                      </div>

                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-[#1E90FF]">
                            Step {log.step}
                          </span>
                          <ChevronRight className="size-3 text-[#8888a0]" />
                          <span className="text-xs font-medium text-white">
                            {log.action}
                          </span>
                          <Badge className={`text-[9px] ${cfg.bg} ${cfg.color} border-0 ml-auto`}>
                            {log.phase}
                          </Badge>
                        </div>
                        {log.input && (
                          <pre className="mt-2 p-2 rounded bg-[#06060F] border border-[#1a1a2e] text-[10px] font-mono text-[#8888a0] overflow-x-auto">
                            {log.input.slice(0, 300)}{log.input.length > 300 ? "…" : ""}
                          </pre>
                        )}
                        {log.output && (
                          <pre className="mt-1 p-2 rounded bg-[#06060F] border border-[#00FF41]/20 text-[10px] font-mono text-[#00d4aa] overflow-x-auto">
                            {log.output.slice(0, 300)}{log.output.length > 300 ? "…" : ""}
                          </pre>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </div>
    </div>
  );
}

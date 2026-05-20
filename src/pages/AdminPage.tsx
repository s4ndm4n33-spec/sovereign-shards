import { useMutation, useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  Shield,
  AlertTriangle,
  Users,
  MessageSquare,
  LogOut,
  Check,
  X,
  Ban,
  RotateCcw,
  Eye,
  EyeOff,
} from "lucide-react";

function AdminLogin({ onLogin }: { onLogin: (token: string) => void }) {
  const login = useMutation(api.admin.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login({ username, password });
      if (result.success && result.token) {
        onLogin(result.token);
      } else {
        setError(result.error ?? "Authentication failed.");
      }
    } catch {
      setError("Connection error.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-shard-red/10 border border-shard-red/20 rounded-lg flex items-center justify-center mx-auto mb-4">
            <Shield className="w-6 h-6 text-shard-red" />
          </div>
          <h1 className="text-xl font-bold text-shard-white font-mono">ADMIN ACCESS</h1>
          <p className="text-xs text-shard-gray font-mono mt-1">RESTRICTED TERMINAL</p>
        </div>
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">USERNAME</label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="h-10 bg-shard-obsidian border-shard-violet/20 font-mono text-sm"
              autoComplete="off"
              required
            />
          </div>
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">PASSWORD</label>
            <div className="relative">
              <Input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-10 bg-shard-obsidian border-shard-violet/20 font-mono text-sm pr-10"
                autoComplete="off"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-shard-gray hover:text-shard-white transition-colors"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          {error && (
            <div className="text-xs text-shard-red bg-shard-red/5 border border-shard-red/20 rounded p-2 font-mono">
              {error}
            </div>
          )}
          <Button
            type="submit"
            disabled={loading}
            className="w-full bg-shard-red hover:bg-shard-red/80 text-white font-mono text-sm"
          >
            {loading ? "AUTHENTICATING..." : "AUTHENTICATE"}
          </Button>
        </form>
      </div>
    </div>
  );
}

function AdminDashboard({ token, onLogout }: { token: string; onLogout: () => void }) {
  const stats = useQuery(api.admin.getStats);
  const appeals = useQuery(api.appeals.listPending);
  const allAppeals = useQuery(api.appeals.listAll);
  const moderatedMessages = useQuery(api.messages.listModerated);
  const profiles = useQuery(api.profiles.listAll);
  const resolveAppeal = useMutation(api.appeals.resolve);
  const restoreMessage = useMutation(api.messages.restoreMessage);
  const setBanned = useMutation(api.profiles.setBanned);
  const logout = useMutation(api.admin.logout);

  const [activeTab, setActiveTab] = useState<"overview" | "appeals" | "moderation" | "users">("overview");

  const handleLogout = useCallback(async () => {
    await logout({ token });
    onLogout();
  }, [logout, token, onLogout]);

  const handleResolveAppeal = useCallback(
    async (appealId: Parameters<typeof resolveAppeal>[0]["appealId"], status: "approved" | "rejected") => {
      await resolveAppeal({ appealId, status, adminResponse: status === "approved" ? "Content restored." : "Appeal denied." });
      toast.success(`Appeal ${status}.`);
    },
    [resolveAppeal],
  );

  const tabs = [
    { id: "overview" as const, label: "OVERVIEW", icon: Shield },
    { id: "appeals" as const, label: `APPEALS${appeals?.length ? ` (${appeals.length})` : ""}`, icon: AlertTriangle },
    { id: "moderation" as const, label: "MODERATION", icon: MessageSquare },
    { id: "users" as const, label: "USERS", icon: Users },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Admin header */}
      <header className="border-b border-shard-red/20 bg-shard-surface px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-shard-red" />
          <span className="font-mono text-sm text-shard-red font-bold tracking-wider">ADMIN TERMINAL</span>
        </div>
        <Button variant="ghost" size="sm" onClick={handleLogout} className="text-shard-gray hover:text-shard-white font-mono text-xs">
          <LogOut className="w-3 h-3 mr-1" />
          LOGOUT
        </Button>
      </header>

      {/* Tabs */}
      <div className="border-b border-shard-violet/10 bg-shard-surface">
        <div className="flex overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-mono border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-shard-violet text-shard-violet"
                  : "border-transparent text-shard-gray hover:text-shard-white"
              }`}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4 sm:p-6 max-w-5xl mx-auto">
        {/* Overview */}
        {activeTab === "overview" && stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {[
              { label: "Total Messages", value: stats.totalMessages, color: "text-shard-cyan" },
              { label: "Moderated", value: stats.moderatedMessages, color: "text-shard-amber" },
              { label: "Pending Appeals", value: stats.pendingAppeals, color: "text-shard-red" },
              { label: "Registered Users", value: stats.totalUsers, color: "text-shard-green" },
              { label: "Banned Users", value: stats.bannedUsers, color: "text-shard-red" },
              { label: "Rooms", value: stats.totalRooms, color: "text-shard-violet" },
            ].map((stat) => (
              <div key={stat.label} className="bg-shard-surface border border-shard-violet/10 rounded-lg p-4">
                <div className={`text-2xl font-bold font-mono ${stat.color}`}>{stat.value}</div>
                <div className="text-xs text-shard-gray font-mono mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Appeals */}
        {activeTab === "appeals" && (
          <div className="space-y-3">
            <h2 className="text-sm font-mono text-shard-white mb-4">PENDING APPEALS</h2>
            {appeals?.length === 0 && (
              <p className="text-shard-gray text-sm font-mono">No pending appeals.</p>
            )}
            {appeals?.map((appeal) => (
              <div key={appeal._id} className="bg-shard-surface border border-shard-violet/10 rounded-lg p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-shard-gray font-mono mb-1">
                      Room: #{appeal.messageRoom ?? "unknown"} • {new Date(appeal._creationTime).toLocaleString()}
                    </div>
                    <div className="text-sm text-shard-white mb-2 bg-shard-obsidian rounded p-2 font-mono text-xs break-all">
                      {appeal.messageContent ?? "[deleted]"}
                    </div>
                    <div className="text-xs text-shard-gray">
                      <span className="text-shard-amber">Appeal reason:</span> {appeal.reason}
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Button
                      size="sm"
                      onClick={() => handleResolveAppeal(appeal._id, "approved")}
                      className="bg-shard-green/20 text-shard-green hover:bg-shard-green/30 h-8"
                    >
                      <Check className="w-3 h-3 mr-1" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleResolveAppeal(appeal._id, "rejected")}
                      className="bg-shard-red/20 text-shard-red hover:bg-shard-red/30 h-8"
                    >
                      <X className="w-3 h-3 mr-1" />
                      Reject
                    </Button>
                  </div>
                </div>
              </div>
            ))}

            {allAppeals && allAppeals.length > 0 && (
              <>
                <h2 className="text-sm font-mono text-shard-white mt-8 mb-4">ALL APPEALS</h2>
                {allAppeals.map((appeal) => (
                  <div key={appeal._id} className="bg-shard-surface border border-shard-violet/10 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-xs font-mono">
                      <span className={
                        appeal.status === "approved" ? "text-shard-green" :
                        appeal.status === "rejected" ? "text-shard-red" :
                        "text-shard-amber"
                      }>
                        [{appeal.status.toUpperCase()}]
                      </span>
                      <span className="text-shard-gray">#{appeal.messageRoom}</span>
                      <span className="text-shard-gray/50">{new Date(appeal._creationTime).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {/* Moderation */}
        {activeTab === "moderation" && (
          <div className="space-y-3">
            <h2 className="text-sm font-mono text-shard-white mb-4">FLAGGED MESSAGES</h2>
            {moderatedMessages?.length === 0 && (
              <p className="text-shard-gray text-sm font-mono">No flagged messages.</p>
            )}
            {moderatedMessages?.map((msg) => (
              <div key={msg._id} className="bg-shard-surface border border-shard-violet/10 rounded-lg p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-shard-gray font-mono mb-1">
                      Room: #{msg.roomName ?? "unknown"} • {new Date(msg._creationTime).toLocaleString()}
                    </div>
                    <div className="text-sm text-shard-white bg-shard-obsidian rounded p-2 font-mono text-xs break-all">
                      {msg.content}
                    </div>
                    <div className="text-xs text-shard-amber mt-1">{msg.moderationReason}</div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={async () => {
                      await restoreMessage({ messageId: msg._id });
                      toast.success("Message restored.");
                    }}
                    className="text-shard-green hover:text-shard-green/80 shrink-0"
                  >
                    <RotateCcw className="w-3 h-3 mr-1" />
                    Restore
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Users */}
        {activeTab === "users" && (
          <div className="space-y-3">
            <h2 className="text-sm font-mono text-shard-white mb-4">REGISTERED OPERATORS</h2>
            {profiles?.length === 0 && (
              <p className="text-shard-gray text-sm font-mono">No registered users yet.</p>
            )}
            {profiles?.map((profile) => (
              <div key={profile._id} className="bg-shard-surface border border-shard-violet/10 rounded-lg p-4 flex items-center gap-4">
                <div
                  className="w-10 h-10 rounded-md flex items-center justify-center text-sm font-bold shrink-0"
                  style={{ backgroundColor: `${profile.avatarColor}20`, color: profile.avatarColor }}
                >
                  {profile.displayName[0]?.toUpperCase() ?? "?"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-shard-white font-medium">{profile.displayName}</div>
                  <div className="text-xs text-shard-gray font-mono">@{profile.handle} • {profile.role}</div>
                  {profile.isBanned && (
                    <div className="text-xs text-shard-red font-mono mt-0.5">BANNED: {profile.banReason}</div>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  {profile.isBanned ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await setBanned({ profileId: profile._id, isBanned: false });
                        toast.success("User unbanned.");
                      }}
                      className="text-shard-green hover:text-shard-green/80 text-xs"
                    >
                      <RotateCcw className="w-3 h-3 mr-1" />
                      Unban
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        const reason = prompt("Ban reason:");
                        if (!reason) return;
                        await setBanned({ profileId: profile._id, isBanned: true, banReason: reason });
                        toast.success("User banned.");
                      }}
                      className="text-shard-red hover:text-shard-red/80 text-xs"
                    >
                      <Ban className="w-3 h-3 mr-1" />
                      Ban
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AdminPage() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("ss-admin-token"));
  const isValid = useQuery(api.admin.validateSession, token ? { token } : "skip");

  useEffect(() => {
    if (isValid === false && token) {
      localStorage.removeItem("ss-admin-token");
      setToken(null);
    }
  }, [isValid, token]);

  const handleLogin = (newToken: string) => {
    localStorage.setItem("ss-admin-token", newToken);
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem("ss-admin-token");
    setToken(null);
  };

  if (!token || isValid === false) {
    return <AdminLogin onLogin={handleLogin} />;
  }

  if (isValid === undefined) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-shard-gray font-mono text-sm animate-pulse">VALIDATING SESSION...</div>
      </div>
    );
  }

  return <AdminDashboard token={token} onLogout={handleLogout} />;
}

import { useMutation, useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/PasswordInput";
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
  UserPlus,
  Trash2,
  Key,
  Crown,
  ShieldCheck,
  Eye,
  Bot,
  Zap,
  Save,
  Power,
  Sliders,
  Link,
  Plus,
  Hash,
  Pencil,
} from "lucide-react";

/* ───────────── LOGIN ───────────── */

function AdminLogin({ onLogin }: { onLogin: (token: string, account: AdminAccount) => void }) {
  const login = useMutation(api.admin.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login({ username, password });
      if (result.success && result.token && result.account) {
        onLogin(result.token, result.account as AdminAccount);
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
                {showPassword ? <X className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
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

/* ───────────── TYPES ───────────── */

interface AdminAccount {
  id: string;
  username: string;
  displayName: string;
  role: string;
}

type Tab = "overview" | "appeals" | "moderation" | "users" | "admins" | "j" | "rooms";

/* ───────────── CREATE ADMIN MODAL ───────────── */

function CreateAdminForm({ onClose }: { onClose: () => void }) {
  const createAccount = useMutation(api.admin.createAccount);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "moderator" | "super_admin">("admin");
  const [loading, setLoading] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await createAccount({
        username,
        password,
        displayName,
        email: email || undefined,
        role,
      });
      if (result.success) {
        toast.success(`Admin "${username}" created.`);
        onClose();
      } else {
        toast.error(result.error ?? "Failed to create admin.");
      }
    } catch {
      toast.error("Connection error.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-shard-surface border border-shard-violet/20 rounded-lg p-5 mb-4">
      <h3 className="text-sm font-mono text-shard-violet mb-4 flex items-center gap-2">
        <UserPlus className="w-4 h-4" />
        CREATE ADMIN ACCOUNT
      </h3>
      <form onSubmit={handleCreate} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">USERNAME *</label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="h-9 bg-shard-obsidian border-shard-violet/20 font-mono text-sm"
              required
            />
          </div>
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">DISPLAY NAME *</label>
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="h-9 bg-shard-obsidian border-shard-violet/20 font-mono text-sm"
              required
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">PASSWORD *</label>
            <PasswordInput
              value={password}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
              className="h-9 bg-shard-obsidian border-shard-violet/20 font-mono text-sm"
              required
            />
          </div>
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">EMAIL</label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-9 bg-shard-obsidian border-shard-violet/20 font-mono text-sm"
            />
          </div>
        </div>
        <div>
          <label className="text-xs text-shard-gray font-mono mb-1 block">ROLE</label>
          <div className="flex gap-2">
            {(["super_admin", "admin", "moderator"] as const).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRole(r)}
                className={`px-3 py-1.5 rounded text-xs font-mono border transition-colors ${
                  role === r
                    ? r === "super_admin"
                      ? "border-shard-amber text-shard-amber bg-shard-amber/10"
                      : r === "admin"
                      ? "border-shard-violet text-shard-violet bg-shard-violet/10"
                      : "border-shard-cyan text-shard-cyan bg-shard-cyan/10"
                    : "border-shard-violet/10 text-shard-gray hover:border-shard-violet/30"
                }`}
              >
                {r === "super_admin" ? "SUPER ADMIN" : r.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
        <div className="flex gap-2 pt-2">
          <Button type="submit" disabled={loading} className="bg-shard-violet hover:bg-shard-violet/80 text-white font-mono text-xs">
            {loading ? "CREATING..." : "CREATE ACCOUNT"}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose} className="font-mono text-xs text-shard-gray">
            CANCEL
          </Button>
        </div>
      </form>
    </div>
  );
}

/* ───────────── DASHBOARD ───────────── */

function AdminDashboard({ token, account, onLogout }: { token: string; account: AdminAccount; onLogout: () => void }) {
  const stats = useQuery(api.admin.getStats);
  const appeals = useQuery(api.appeals.listPending);
  const allAppeals = useQuery(api.appeals.listAll);
  const moderatedMessages = useQuery(api.messages.listModerated);
  const profiles = useQuery(api.profiles.listAll);
  const adminAccounts = useQuery(api.admin.listAccounts);
  const allRooms = useQuery(api.rooms.list);
  const jConfig = useQuery(api.systemAI.getConfig);
  const resolveAppeal = useMutation(api.appeals.resolve);
  const restoreMessage = useMutation(api.messages.restoreMessage);
  const setBanned = useMutation(api.profiles.setBanned);
  const updateAdminAccount = useMutation(api.admin.updateAccount);
  const deleteAdminAccount = useMutation(api.admin.deleteAccount);
  const createRoom = useMutation(api.rooms.createRoom);
  const updateRoom = useMutation(api.rooms.updateRoom);
  const deleteRoom = useMutation(api.rooms.deleteRoom);
  const ensureJ = useMutation(api.systemAI.ensureJ);
  const updateJProviders = useMutation(api.systemAI.updateProviders);
  const updateJHeuristics = useMutation(api.systemAI.updateHeuristics);
  const updateJProfile = useMutation(api.systemAI.updateProfile);
  const setJActive = useMutation(api.systemAI.setActive);
  const logout = useMutation(api.admin.logout);

  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [showCreateAdmin, setShowCreateAdmin] = useState(false);

  // Ensure J exists on mount
  useEffect(() => {
    ensureJ();
  }, [ensureJ]);

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

  const isSuperAdmin = account.role === "super_admin";

  const tabs = [
    { id: "overview" as const, label: "OVERVIEW", icon: Shield },
    { id: "j" as const, label: `J${jConfig?.isActive ? " ◉" : ""}`, icon: Bot },
    { id: "appeals" as const, label: `APPEALS${appeals?.length ? ` (${appeals.length})` : ""}`, icon: AlertTriangle },
    { id: "moderation" as const, label: "MODERATION", icon: MessageSquare },
    { id: "users" as const, label: "USERS", icon: Users },
    ...(account.role === "super_admin" ? [{ id: "rooms" as const, label: `ROOMS (${allRooms?.length ?? 0})`, icon: Hash }] : []),
    { id: "admins" as const, label: "ADMINS", icon: Key },
  ];

  const roleIcon = (role: string) => {
    if (role === "super_admin") return <Crown className="w-3 h-3 text-shard-amber" />;
    if (role === "admin") return <ShieldCheck className="w-3 h-3 text-shard-violet" />;
    return <Eye className="w-3 h-3 text-shard-cyan" />;
  };

  const roleColor = (role: string) => {
    if (role === "super_admin") return "text-shard-amber";
    if (role === "admin") return "text-shard-violet";
    return "text-shard-cyan";
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Admin header */}
      <header className="border-b border-shard-red/20 bg-shard-surface px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-shard-red" />
          <span className="font-mono text-sm text-shard-red font-bold tracking-wider">ADMIN TERMINAL</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-mono">
            {roleIcon(account.role)}
            <span className={roleColor(account.role)}>{account.displayName}</span>
            <span className="text-shard-gray/40">({account.role.replace("_", " ")})</span>
          </div>
          <Button variant="ghost" size="sm" onClick={handleLogout} className="text-shard-gray hover:text-shard-white font-mono text-xs">
            <LogOut className="w-3 h-3 mr-1" />
            LOGOUT
          </Button>
        </div>
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
        {/* ─── Overview ─── */}
        {activeTab === "overview" && stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {[
              { label: "Total Messages", value: stats.totalMessages, color: "text-shard-cyan", tab: null },
              { label: "Moderated", value: stats.moderatedMessages, color: "text-shard-amber", tab: "moderation" as Tab },
              { label: "Pending Appeals", value: stats.pendingAppeals, color: "text-shard-red", tab: "appeals" as Tab },
              { label: "Registered Users", value: stats.totalUsers, color: "text-shard-green", tab: "users" as Tab },
              { label: "Banned Users", value: stats.bannedUsers, color: "text-shard-red", tab: "users" as Tab },
              { label: "Rooms", value: stats.totalRooms, color: "text-shard-violet", tab: account.role === "super_admin" ? ("rooms" as Tab) : null },
              { label: "Admin Accounts", value: stats.totalAdmins, color: "text-shard-amber", tab: "admins" as Tab },
              { label: "J — System AI", value: jConfig?.isActive ? "ONLINE" : "OFFLINE", color: jConfig?.isActive ? "text-shard-cyan" : "text-shard-red", tab: "j" as Tab },
            ].map((stat) => (
              <button
                key={stat.label}
                onClick={() => stat.tab && setActiveTab(stat.tab)}
                className={`bg-shard-surface border border-shard-violet/10 rounded-lg p-4 text-left transition-all ${
                  stat.tab
                    ? "hover:border-shard-violet/30 hover:bg-shard-surface/80 cursor-pointer"
                    : "cursor-default"
                }`}
              >
                <div className={`text-2xl font-bold font-mono ${stat.color}`}>{stat.value}</div>
                <div className="text-xs text-shard-gray font-mono mt-1">{stat.label}</div>
                {stat.tab && (
                  <div className="text-[10px] text-shard-violet/50 font-mono mt-2">→ VIEW</div>
                )}
              </button>
            ))}
          </div>
        )}

        {/* ─── Appeals ─── */}
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

        {/* ─── Moderation ─── */}
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

        {/* ─── Users ─── */}
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

        {/* ─── Admin Accounts ─── */}
        {activeTab === "admins" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-mono text-shard-white">ADMIN ACCOUNTS</h2>
              {isSuperAdmin && (
                <Button
                  size="sm"
                  onClick={() => setShowCreateAdmin(!showCreateAdmin)}
                  className="bg-shard-violet hover:bg-shard-violet/80 text-white font-mono text-xs"
                >
                  <UserPlus className="w-3 h-3 mr-1" />
                  {showCreateAdmin ? "CANCEL" : "CREATE ADMIN"}
                </Button>
              )}
            </div>

            {showCreateAdmin && <CreateAdminForm onClose={() => setShowCreateAdmin(false)} />}

            {adminAccounts?.length === 0 && (
              <p className="text-shard-gray text-sm font-mono">No admin accounts yet.</p>
            )}
            {adminAccounts?.map((admin: any) => (
              <div key={admin._id} className="bg-shard-surface border border-shard-violet/10 rounded-lg p-4 flex items-center gap-4">
                <div className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 bg-shard-obsidian border border-shard-violet/10">
                  {roleIcon(admin.role)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-shard-white font-medium">{admin.displayName}</span>
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                      admin.role === "super_admin"
                        ? "border-shard-amber/30 text-shard-amber bg-shard-amber/5"
                        : admin.role === "admin"
                        ? "border-shard-violet/30 text-shard-violet bg-shard-violet/5"
                        : "border-shard-cyan/30 text-shard-cyan bg-shard-cyan/5"
                    }`}>
                      {admin.role.replace("_", " ").toUpperCase()}
                    </span>
                    {!admin.isActive && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-shard-red/30 text-shard-red bg-shard-red/5">
                        DEACTIVATED
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-shard-gray font-mono mt-0.5">
                    @{admin.username}
                    {admin.email && <span className="text-shard-gray/40"> • {admin.email}</span>}
                  </div>
                  <div className="text-[10px] text-shard-gray/30 font-mono mt-0.5">
                    Created: {new Date(admin._creationTime).toLocaleDateString()}
                    {admin.lastLoginAt && <span> • Last login: {new Date(admin.lastLoginAt).toLocaleString()}</span>}
                  </div>
                </div>
                {isSuperAdmin && admin._id !== account.id && (
                  <div className="flex gap-2 shrink-0">
                    {admin.isActive ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={async () => {
                          await updateAdminAccount({ accountId: admin._id, isActive: false });
                          toast.success("Admin deactivated.");
                        }}
                        className="text-shard-amber hover:text-shard-amber/80 text-xs"
                        title="Deactivate"
                      >
                        <Ban className="w-3 h-3" />
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={async () => {
                          await updateAdminAccount({ accountId: admin._id, isActive: true });
                          toast.success("Admin reactivated.");
                        }}
                        className="text-shard-green hover:text-shard-green/80 text-xs"
                        title="Reactivate"
                      >
                        <RotateCcw className="w-3 h-3" />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        if (!confirm(`Delete admin account @${admin.username}?`)) return;
                        const result = await deleteAdminAccount({ accountId: admin._id });
                        if (result.success) {
                          toast.success("Admin deleted.");
                        } else {
                          toast.error(result.error ?? "Failed to delete.");
                        }
                      }}
                      className="text-shard-red hover:text-shard-red/80 text-xs"
                      title="Delete"
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ─── Rooms (super_admin only) ─── */}
        {activeTab === "rooms" && account.role === "super_admin" && (
          <RoomsPanel
            rooms={allRooms ?? []}
            createRoom={createRoom}
            updateRoom={updateRoom}
            deleteRoom={deleteRoom}
          />
        )}

        {/* ─── J — System AI ─── */}
        {activeTab === "j" && (
          <JConfigPanel
            jConfig={jConfig}
            updateProviders={updateJProviders}
            updateHeuristics={updateJHeuristics}
            updateProfile={updateJProfile}
            setActive={setJActive}
          />
        )}
      </div>
    </div>
  );
}

/* ───────────── ROOMS PANEL ───────────── */

function RoomsPanel({
  rooms,
  createRoom,
  updateRoom,
  deleteRoom,
}: {
  rooms: any[];
  createRoom: any;
  updateRoom: any;
  deleteRoom: any;
}) {
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newIcon, setNewIcon] = useState("◆");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editIcon, setEditIcon] = useState("");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-mono text-shard-white">ROOMS ({rooms.length})</h2>
        <Button
          onClick={() => setShowCreate(!showCreate)}
          className="bg-shard-violet hover:bg-shard-violet/80 text-white font-mono text-xs"
        >
          <Plus className="w-3 h-3 mr-1" />
          CREATE ROOM
        </Button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-shard-surface border border-shard-violet/20 rounded-lg p-4 space-y-3">
          <h3 className="text-xs font-mono text-shard-cyan">NEW ROOM</h3>
          <div className="grid grid-cols-[60px_1fr] gap-3">
            <div>
              <label className="text-[10px] text-shard-gray font-mono mb-1 block">ICON</label>
              <Input
                value={newIcon}
                onChange={(e) => setNewIcon(e.target.value)}
                className="h-9 bg-shard-obsidian border-shard-violet/20 text-center text-lg"
                maxLength={2}
              />
            </div>
            <div>
              <label className="text-[10px] text-shard-gray font-mono mb-1 block">NAME</label>
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="room-name"
                className="h-9 bg-shard-obsidian border-shard-violet/20 text-sm font-mono"
              />
            </div>
          </div>
          <div>
            <label className="text-[10px] text-shard-gray font-mono mb-1 block">DESCRIPTION</label>
            <Input
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="What's this room for?"
              className="h-9 bg-shard-obsidian border-shard-violet/20 text-sm font-mono"
            />
          </div>
          <div className="flex gap-2">
            <Button
              onClick={async () => {
                if (!newName.trim()) { toast.error("Room needs a name."); return; }
                await createRoom({ name: newName.trim(), description: newDesc.trim() || "New room.", icon: newIcon || "◆" });
                toast.success(`Room #${newName.trim().toLowerCase().replace(/\s+/g, "-")} created.`);
                setNewName(""); setNewDesc(""); setNewIcon("◆"); setShowCreate(false);
              }}
              className="bg-shard-cyan hover:bg-shard-cyan/80 text-shard-obsidian font-mono text-xs"
            >
              CREATE
            </Button>
            <Button
              variant="ghost"
              onClick={() => setShowCreate(false)}
              className="text-shard-gray font-mono text-xs"
            >
              CANCEL
            </Button>
          </div>
        </div>
      )}

      {/* Room list */}
      <div className="space-y-2">
        {rooms.map((room) => (
          <div key={room._id} className="bg-shard-surface border border-shard-violet/10 rounded-lg p-3">
            {editingId === room._id ? (
              /* Edit mode */
              <div className="space-y-2">
                <div className="grid grid-cols-[60px_1fr] gap-2">
                  <Input
                    value={editIcon}
                    onChange={(e) => setEditIcon(e.target.value)}
                    className="h-8 bg-shard-obsidian border-shard-violet/20 text-center text-lg"
                    maxLength={2}
                  />
                  <Input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="h-8 bg-shard-obsidian border-shard-violet/20 text-sm font-mono"
                  />
                </div>
                <Input
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  className="h-8 bg-shard-obsidian border-shard-violet/20 text-xs font-mono"
                />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={async () => {
                      await updateRoom({ roomId: room._id, name: editName, description: editDesc, icon: editIcon });
                      toast.success("Room updated.");
                      setEditingId(null);
                    }}
                    className="bg-shard-cyan hover:bg-shard-cyan/80 text-shard-obsidian font-mono text-[10px] h-7"
                  >
                    SAVE
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditingId(null)} className="text-shard-gray font-mono text-[10px] h-7">
                    CANCEL
                  </Button>
                </div>
              </div>
            ) : (
              /* Display mode */
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-lg">{room.icon}</span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono font-bold text-shard-white">#{room.name}</span>
                      {room.isDefault && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-shard-violet/10 text-shard-violet border border-shard-violet/20">DEFAULT</span>
                      )}
                    </div>
                    <p className="text-[11px] text-shard-gray font-mono">{room.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setEditingId(room._id);
                      setEditName(room.name);
                      setEditDesc(room.description);
                      setEditIcon(room.icon);
                    }}
                    className="text-shard-cyan hover:text-shard-cyan/80 text-xs"
                    title="Edit"
                  >
                    <Pencil className="w-3 h-3" />
                  </Button>
                  {!room.isDefault && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        if (!confirm(`Delete room #${room.name}? This cannot be undone.`)) return;
                        const result = await deleteRoom({ roomId: room._id });
                        if (result.success) toast.success("Room deleted.");
                        else toast.error("Cannot delete this room.");
                      }}
                      className="text-shard-red hover:text-shard-red/80 text-xs"
                      title="Delete"
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ───────────── J CONFIG PANEL ───────────── */

function JConfigPanel({
  jConfig,
  updateProviders,
  updateHeuristics,
  updateProfile,
  setActive,
}: {
  jConfig: any;
  updateProviders: any;
  updateHeuristics: any;
  updateProfile: any;
  setActive: any;
}) {
  // Provider keys
  const [geminiKey, setGeminiKey] = useState("");
  const [groqKey, setGroqKey] = useState("");
  const [cerebrasKey, setCerebrasKey] = useState("");
  const [defaultModel, setDefaultModel] = useState("gemini-2.0-flash");
  const [tokenBudget, setTokenBudget] = useState(4096);
  const [systemPromptOverride, setSystemPromptOverride] = useState("");

  // Heuristic state
  const [sensitivity, setSensitivity] = useState(0.7);
  const [responseStyle, setResponseStyle] = useState("tactical");
  const [autoModerate, setAutoModerate] = useState(true);
  const [greetNewUsers, setGreetNewUsers] = useState(true);
  const [maxResponseLength, setMaxResponseLength] = useState(500);
  const [personality, setPersonality] = useState("");

  // Profile state
  const [displayName, setDisplayName] = useState("J");
  const [bio, setBio] = useState("");

  const [initialized, setInitialized] = useState(false);

  // Sync from server
  useEffect(() => {
    if (jConfig && !initialized) {
      setDefaultModel(jConfig.defaultModel ?? "gemini-2.0-flash");
      setTokenBudget(jConfig.tokenBudget ?? 4096);
      setSystemPromptOverride(jConfig.systemPromptOverride ?? "");
      setSensitivity(jConfig.moderationSensitivity);
      setResponseStyle(jConfig.responseStyle);
      setAutoModerate(jConfig.autoModerate);
      setGreetNewUsers(jConfig.greetNewUsers);
      setMaxResponseLength(jConfig.maxResponseLength);
      setPersonality(jConfig.personality);
      setDisplayName(jConfig.displayName);
      setBio(jConfig.bio);
      setInitialized(true);
    }
  }, [jConfig, initialized]);

  if (!jConfig) {
    return <div className="text-shard-gray font-mono text-sm animate-pulse">INITIALIZING J...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header with status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-lg flex items-center justify-center border-2"
            style={{ backgroundColor: `${jConfig.avatarColor}15`, borderColor: `${jConfig.avatarColor}40` }}>
            <Bot className="w-6 h-6" style={{ color: jConfig.avatarColor }} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-shard-white font-mono">{jConfig.displayName}</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-shard-cyan/30 text-shard-cyan bg-shard-cyan/5">
                SYSTEM AI
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-shard-violet/30 text-shard-violet bg-shard-violet/5">
                MOD
              </span>
            </div>
            <p className="text-xs text-shard-gray font-mono">{jConfig.bio}</p>
          </div>
        </div>
        <Button
          onClick={async () => {
            await setActive({ isActive: !jConfig.isActive });
            toast.success(jConfig.isActive ? "J deactivated." : "J activated.");
          }}
          className={`font-mono text-xs ${
            jConfig.isActive
              ? "bg-shard-green/20 text-shard-green hover:bg-shard-green/30 border border-shard-green/30"
              : "bg-shard-red/20 text-shard-red hover:bg-shard-red/30 border border-shard-red/30"
          }`}
        >
          <Power className="w-3 h-3 mr-1" />
          {jConfig.isActive ? "ONLINE" : "OFFLINE"}
        </Button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-shard-surface border border-shard-violet/10 rounded-lg p-3 text-center">
          <div className="text-lg font-bold font-mono text-shard-cyan">{jConfig.totalInvocations}</div>
          <div className="text-[10px] text-shard-gray font-mono">INVOCATIONS</div>
        </div>
        <div className="bg-shard-surface border border-shard-violet/10 rounded-lg p-3 text-center">
          <div className="text-sm font-bold font-mono text-shard-violet truncate">{jConfig.defaultModel || "—"}</div>
          <div className="text-[10px] text-shard-gray font-mono">DEFAULT MODEL</div>
        </div>
        <div className="bg-shard-surface border border-shard-violet/10 rounded-lg p-3 text-center">
          <div className="flex justify-center gap-1.5 mb-0.5">
            <span className={`w-2 h-2 rounded-full ${jConfig.hasGeminiKey ? "bg-shard-green" : "bg-shard-gray/30"}`} title="Gemini" />
            <span className={`w-2 h-2 rounded-full ${jConfig.hasGroqKey ? "bg-shard-green" : "bg-shard-gray/30"}`} title="Groq" />
            <span className={`w-2 h-2 rounded-full ${jConfig.hasCerebrasKey ? "bg-shard-green" : "bg-shard-gray/30"}`} title="Cerebras" />
          </div>
          <div className="text-[10px] text-shard-gray font-mono">PROVIDERS</div>
        </div>
        <div className="bg-shard-surface border border-shard-violet/10 rounded-lg p-3 text-center">
          <div className={`text-lg font-bold font-mono ${jConfig.isActive ? "text-shard-green" : "text-shard-red"}`}>
            {jConfig.isActive ? "ACTIVE" : "INACTIVE"}
          </div>
          <div className="text-[10px] text-shard-gray font-mono">STATUS</div>
        </div>
      </div>

      {/* Configuration — Multi-Provider */}
      <div className="bg-shard-surface border border-shard-violet/10 rounded-lg p-5">
        <h3 className="text-sm font-mono text-shard-cyan mb-1 flex items-center gap-2">
          <Link className="w-4 h-4" />
          CONFIGURATION
        </h3>
        <p className="text-[10px] text-shard-gray/60 font-mono mb-4">Edit any setting below. Changes take effect immediately.</p>

        <div className="space-y-4">
          {/* Gemini — Primary */}
          <div className="p-3 rounded-lg border border-shard-cyan/15 bg-shard-obsidian/50">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-shard-cyan">GEMINI API KEY</span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-shard-cyan/10 text-shard-cyan border border-shard-cyan/20">PRIMARY</span>
              </div>
              {jConfig.hasGeminiKey && <span className="text-[10px] font-mono text-shard-green">● SET</span>}
            </div>
            <PasswordInput
              value={geminiKey}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGeminiKey(e.target.value)}
              placeholder={jConfig.hasGeminiKey ? "••••••••  (key set)" : "AIza..."}
              className="h-9 bg-shard-obsidian border-shard-violet/20 text-sm font-mono mb-1"
            />
            <p className="text-[10px] text-shard-gray/40 font-mono">
              Free key from <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="text-shard-cyan/60 hover:text-shard-cyan underline">aistudio.google.com/apikey</a> — 1,500 req/day. Primary provider.
            </p>
          </div>

          {/* Groq — Fallback */}
          <div className="p-3 rounded-lg border border-shard-violet/15 bg-shard-obsidian/50">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-shard-violet">GROQ API KEY</span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-shard-violet/10 text-shard-violet border border-shard-violet/20">FALLBACK</span>
              </div>
              {jConfig.hasGroqKey && <span className="text-[10px] font-mono text-shard-green">● SET</span>}
            </div>
            <PasswordInput
              value={groqKey}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGroqKey(e.target.value)}
              placeholder={jConfig.hasGroqKey ? "••••••••  (key set)" : "gsk_..."}
              className="h-9 bg-shard-obsidian border-shard-violet/20 text-sm font-mono mb-1"
            />
            <p className="text-[10px] text-shard-gray/40 font-mono">
              Free key from <a href="https://console.groq.com" target="_blank" rel="noreferrer" className="text-shard-violet/60 hover:text-shard-violet underline">console.groq.com</a> — auto-fallback if Gemini is down.
            </p>
          </div>

          {/* Cerebras — Fallback */}
          <div className="p-3 rounded-lg border border-shard-amber/15 bg-shard-obsidian/50">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-shard-amber">CEREBRAS API KEY</span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-shard-amber/10 text-shard-amber border border-shard-amber/20">FALLBACK</span>
              </div>
              {jConfig.hasCerebrasKey && <span className="text-[10px] font-mono text-shard-green">● SET</span>}
            </div>
            <PasswordInput
              value={cerebrasKey}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCerebrasKey(e.target.value)}
              placeholder={jConfig.hasCerebrasKey ? "••••••••  (key set)" : "csk-..."}
              className="h-9 bg-shard-obsidian border-shard-violet/20 text-sm font-mono mb-1"
            />
            <p className="text-[10px] text-shard-gray/40 font-mono">
              Free key from <a href="https://cerebras.ai" target="_blank" rel="noreferrer" className="text-shard-amber/60 hover:text-shard-amber underline">cerebras.ai</a> — third fallback provider.
            </p>
          </div>

          {/* Default Model + Token Budget */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-shard-gray font-mono mb-1 block">DEFAULT MODEL</label>
              <Input
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
                placeholder="gemini-2.0-flash"
                className="h-9 bg-shard-obsidian border-shard-violet/20 text-sm font-mono"
              />
              <p className="text-[10px] text-shard-gray/40 font-mono mt-0.5">
                Primary: gemini-2.0-flash. Also: gemini-2.0-flash-lite, llama-3.1-8b-instant
              </p>
            </div>
            <div>
              <label className="text-xs text-shard-gray font-mono mb-1 block">TOKEN BUDGET</label>
              <Input
                type="number"
                value={tokenBudget}
                onChange={(e) => setTokenBudget(Math.min(parseInt(e.target.value) || 0, 4096))}
                className="h-9 bg-shard-obsidian border-shard-violet/20 text-sm font-mono"
              />
              <p className="text-[10px] text-shard-gray/40 font-mono mt-0.5">
                Max context window (J's hard cap is 4096)
              </p>
            </div>
          </div>

          {/* System Prompt Override */}
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">SYSTEM PROMPT OVERRIDE</label>
            <textarea
              value={systemPromptOverride}
              onChange={(e) => setSystemPromptOverride(e.target.value)}
              rows={3}
              className="w-full bg-shard-obsidian border border-shard-violet/20 rounded-md px-3 py-2 text-sm font-mono text-shard-white resize-none focus:outline-none focus:border-shard-violet/40"
              placeholder="Custom system prompt — leave empty for default J personality"
            />
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap gap-2 pt-1">
            <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer"
              className="text-[10px] font-mono px-2 py-1 rounded border border-shard-cyan/20 text-shard-cyan hover:bg-shard-cyan/10 transition-colors">
              Get Gemini API Key →
            </a>
            <a href="https://console.groq.com" target="_blank" rel="noreferrer"
              className="text-[10px] font-mono px-2 py-1 rounded border border-shard-violet/20 text-shard-violet hover:bg-shard-violet/10 transition-colors">
              Get Groq API Key →
            </a>
            <a href="https://cerebras.ai" target="_blank" rel="noreferrer"
              className="text-[10px] font-mono px-2 py-1 rounded border border-shard-amber/20 text-shard-amber hover:bg-shard-amber/10 transition-colors">
              Get Cerebras API Key →
            </a>
            <a href="https://github.com/s4ndm4n33-spec/sovereign-shards" target="_blank" rel="noreferrer"
              className="text-[10px] font-mono px-2 py-1 rounded border border-shard-gray/20 text-shard-gray hover:bg-shard-gray/10 transition-colors">
              GitHub Repo →
            </a>
          </div>

          <Button
            onClick={async () => {
              const updates: any = {
                defaultModel: defaultModel || undefined,
                tokenBudget,
                systemPromptOverride: systemPromptOverride || undefined,
              };
              if (geminiKey) updates.geminiApiKey = geminiKey;
              if (groqKey) updates.groqApiKey = groqKey;
              if (cerebrasKey) updates.cerebrasApiKey = cerebrasKey;
              await updateProviders(updates);
              setGeminiKey("");
              setGroqKey("");
              setCerebrasKey("");
              toast.success("Configuration saved.");
            }}
            className="bg-shard-cyan hover:bg-shard-cyan/80 text-shard-obsidian font-mono text-xs"
          >
            <Save className="w-3 h-3 mr-1" />
            SAVE CONFIGURATION
          </Button>
        </div>
      </div>

      {/* Heuristic Calibration */}
      <div className="bg-shard-surface border border-shard-violet/10 rounded-lg p-5">
        <h3 className="text-sm font-mono text-shard-violet mb-4 flex items-center gap-2">
          <Sliders className="w-4 h-4" />
          HEURISTIC CALIBRATION
        </h3>
        <div className="space-y-4">
          {/* Moderation Sensitivity */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-shard-gray font-mono">MODERATION SENSITIVITY</label>
              <span className="text-xs font-mono text-shard-violet">{(sensitivity * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={sensitivity}
              onChange={(e) => setSensitivity(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-shard-obsidian rounded-full appearance-none cursor-pointer accent-shard-violet"
            />
            <div className="flex justify-between text-[10px] text-shard-gray/40 font-mono mt-0.5">
              <span>PERMISSIVE</span>
              <span>STRICT</span>
            </div>
          </div>

          {/* Response Style */}
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1.5 block">RESPONSE STYLE</label>
            <div className="flex gap-2">
              {["tactical", "conversational", "minimal"].map((style) => (
                <button
                  key={style}
                  onClick={() => setResponseStyle(style)}
                  className={`px-3 py-1.5 rounded text-xs font-mono border transition-colors ${
                    responseStyle === style
                      ? "border-shard-violet text-shard-violet bg-shard-violet/10"
                      : "border-shard-violet/10 text-shard-gray hover:border-shard-violet/30"
                  }`}
                >
                  {style.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Max Response Length */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-shard-gray font-mono">MAX RESPONSE LENGTH</label>
              <span className="text-xs font-mono text-shard-violet">{maxResponseLength}</span>
            </div>
            <input
              type="range"
              min="50"
              max="2000"
              step="50"
              value={maxResponseLength}
              onChange={(e) => setMaxResponseLength(parseInt(e.target.value))}
              className="w-full h-1.5 bg-shard-obsidian rounded-full appearance-none cursor-pointer accent-shard-violet"
            />
            <div className="flex justify-between text-[10px] text-shard-gray/40 font-mono mt-0.5">
              <span>TERSE</span>
              <span>VERBOSE</span>
            </div>
          </div>

          {/* Toggles */}
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setAutoModerate(!autoModerate)}
              className={`p-3 rounded-lg border text-left transition-colors ${
                autoModerate
                  ? "border-shard-green/30 bg-shard-green/5"
                  : "border-shard-violet/10 bg-shard-surface"
              }`}
            >
              <div className={`text-xs font-mono font-bold ${autoModerate ? "text-shard-green" : "text-shard-gray"}`}>
                AUTO-MODERATE
              </div>
              <div className="text-[10px] text-shard-gray/50 font-mono mt-0.5">
                Flag content without human review
              </div>
            </button>
            <button
              onClick={() => setGreetNewUsers(!greetNewUsers)}
              className={`p-3 rounded-lg border text-left transition-colors ${
                greetNewUsers
                  ? "border-shard-green/30 bg-shard-green/5"
                  : "border-shard-violet/10 bg-shard-surface"
              }`}
            >
              <div className={`text-xs font-mono font-bold ${greetNewUsers ? "text-shard-green" : "text-shard-gray"}`}>
                GREET OPERATORS
              </div>
              <div className="text-[10px] text-shard-gray/50 font-mono mt-0.5">
                Welcome new operators on arrival
              </div>
            </button>
          </div>

          {/* Personality */}
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">PERSONALITY DIRECTIVE</label>
            <textarea
              value={personality}
              onChange={(e) => setPersonality(e.target.value)}
              rows={3}
              className="w-full bg-shard-obsidian border border-shard-violet/20 rounded-md px-3 py-2 text-sm font-mono text-shard-white resize-none focus:outline-none focus:border-shard-violet/40"
              placeholder="Define J's personality and behavioral parameters..."
            />
          </div>

          <Button
            onClick={async () => {
              await updateHeuristics({
                moderationSensitivity: sensitivity,
                responseStyle,
                autoModerate,
                greetNewUsers,
                maxResponseLength,
                personality,
              });
              toast.success("Heuristics calibrated.");
            }}
            className="bg-shard-violet hover:bg-shard-violet/80 text-white font-mono text-xs"
          >
            <Zap className="w-3 h-3 mr-1" />
            APPLY CALIBRATION
          </Button>
        </div>
      </div>

      {/* Profile Config */}
      <div className="bg-shard-surface border border-shard-violet/10 rounded-lg p-5">
        <h3 className="text-sm font-mono text-shard-amber mb-4 flex items-center gap-2">
          <Bot className="w-4 h-4" />
          PERSONA
        </h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">DISPLAY NAME</label>
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="h-9 bg-shard-obsidian border-shard-violet/20 text-sm font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">BIO</label>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              rows={2}
              className="w-full bg-shard-obsidian border border-shard-violet/20 rounded-md px-3 py-2 text-sm font-mono text-shard-white resize-none focus:outline-none focus:border-shard-violet/40"
            />
          </div>
          <Button
            onClick={async () => {
              await updateProfile({ displayName, bio });
              toast.success("Persona updated.");
            }}
            className="bg-shard-amber hover:bg-shard-amber/80 text-shard-obsidian font-mono text-xs"
          >
            <Save className="w-3 h-3 mr-1" />
            SAVE PERSONA
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ───────────── PAGE ───────────── */

export function AdminPage() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("ss-admin-token"));
  const [account, setAccount] = useState<AdminAccount | null>(() => {
    try {
      const stored = localStorage.getItem("ss-admin-account");
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const sessionCheck = useQuery(api.admin.validateSession, token ? { token } : "skip");

  useEffect(() => {
    if (sessionCheck && !sessionCheck.valid && token) {
      localStorage.removeItem("ss-admin-token");
      localStorage.removeItem("ss-admin-account");
      setToken(null);
      setAccount(null);
    }
    // Sync account from server if session is valid
    if (sessionCheck?.valid && sessionCheck.account) {
      setAccount(sessionCheck.account as AdminAccount);
      localStorage.setItem("ss-admin-account", JSON.stringify(sessionCheck.account));
    }
  }, [sessionCheck, token]);

  const handleLogin = (newToken: string, newAccount: AdminAccount) => {
    localStorage.setItem("ss-admin-token", newToken);
    localStorage.setItem("ss-admin-account", JSON.stringify(newAccount));
    setToken(newToken);
    setAccount(newAccount);
  };

  const handleLogout = () => {
    localStorage.removeItem("ss-admin-token");
    localStorage.removeItem("ss-admin-account");
    setToken(null);
    setAccount(null);
  };

  if (!token || (sessionCheck && !sessionCheck.valid)) {
    return <AdminLogin onLogin={handleLogin} />;
  }

  if (sessionCheck === undefined) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-shard-gray font-mono text-sm animate-pulse">VALIDATING SESSION...</div>
      </div>
    );
  }

  if (!account) {
    return <AdminLogin onLogin={handleLogin} />;
  }

  return <AdminDashboard token={token} account={account} onLogout={handleLogout} />;
}

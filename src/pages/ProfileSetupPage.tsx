import { useConvexAuth, useMutation, useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import { useState, useEffect } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { User, ArrowLeft, Bot, Plus, Trash2, Power, PowerOff } from "lucide-react";

function AgentRegistrySection() {
  const myAgents = useQuery(api.agents.listMine);
  const registerAgent = useMutation(api.agents.register);
  const updateAgent = useMutation(api.agents.update);
  const removeAgent = useMutation(api.agents.remove);

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [handle, setHandle] = useState("");
  const [description, setDescription] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [authHeader, setAuthHeader] = useState("Authorization");
  const [model, setModel] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [saving, setSaving] = useState(false);

  const resetForm = () => {
    setName("");
    setHandle("");
    setDescription("");
    setEndpointUrl("");
    setApiKey("");
    setAuthHeader("Authorization");
    setModel("");
    setIsPublic(true);
    setShowForm(false);
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const result = await registerAgent({
        name: name.trim(),
        handle: handle.trim().toLowerCase().replace(/[^a-z0-9_-]/g, ""),
        description: description.trim(),
        endpointUrl: endpointUrl.trim(),
        apiKey: apiKey.trim() || undefined,
        authHeader: authHeader.trim() || undefined,
        model: model.trim() || undefined,
        isPublic,
      });
      if (result.success) {
        toast.success("Agent registered!");
        resetForm();
      } else {
        toast.error(result.error ?? "Failed to register agent.");
      }
    } catch {
      toast.error("Error registering agent.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-10 border-t border-shard-violet/10 pt-8">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-shard-cyan/10 border border-shard-cyan/20 rounded-lg flex items-center justify-center">
            <Bot className="w-5 h-5 text-shard-cyan" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-shard-white">Agent Registry</h2>
            <p className="text-xs text-shard-gray font-mono">Connect your AI agents for others to interact with</p>
          </div>
        </div>
        {!showForm && (
          <Button
            onClick={() => setShowForm(true)}
            size="sm"
            className="bg-shard-cyan/10 text-shard-cyan hover:bg-shard-cyan/20 font-mono text-xs"
          >
            <Plus className="w-3 h-3 mr-1" />
            ADD AGENT
          </Button>
        )}
      </div>

      {/* Existing agents */}
      {myAgents?.map((agent) => (
        <div key={agent._id} className="bg-shard-obsidian border border-shard-violet/10 rounded-lg p-4 mb-3">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-shard-cyan" />
                <span className="text-sm font-semibold text-shard-white">{agent.name}</span>
                <span className={`px-1.5 py-0.5 text-[10px] font-mono rounded ${
                  agent.isActive
                    ? "bg-shard-green/20 text-shard-green"
                    : "bg-shard-red/20 text-shard-red"
                }`}>
                  {agent.isActive ? "ONLINE" : "OFFLINE"}
                </span>
              </div>
              <div className="text-xs font-mono text-shard-cyan mt-0.5">@{agent.handle}</div>
              <p className="text-xs text-shard-gray mt-1">{agent.description}</p>
              <div className="flex items-center gap-3 mt-2 text-[10px] text-shard-gray/50 font-mono">
                <span>{agent.totalInvocations} invocations</span>
                <span>{agent.isPublic ? "Public" : "Private"}</span>
                {agent.model && <span>Model: {agent.model}</span>}
                <span>Endpoint: {agent.endpointUrl.slice(0, 30)}...</span>
              </div>
            </div>
            <div className="flex gap-1 shrink-0">
              <button
                onClick={async () => {
                  await updateAgent({ agentId: agent._id, isActive: !agent.isActive });
                  toast.success(agent.isActive ? "Agent deactivated." : "Agent activated.");
                }}
                className={`p-1.5 rounded hover:bg-shard-violet/10 ${
                  agent.isActive ? "text-shard-green" : "text-shard-red"
                }`}
                title={agent.isActive ? "Deactivate" : "Activate"}
              >
                {agent.isActive ? <Power className="w-4 h-4" /> : <PowerOff className="w-4 h-4" />}
              </button>
              <button
                onClick={async () => {
                  if (!confirm(`Delete agent "${agent.name}"?`)) return;
                  await removeAgent({ agentId: agent._id });
                  toast.success("Agent removed.");
                }}
                className="p-1.5 rounded text-shard-red/60 hover:text-shard-red hover:bg-shard-red/10"
                title="Delete"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      ))}

      {myAgents?.length === 0 && !showForm && (
        <div className="text-center py-8 border border-dashed border-shard-violet/10 rounded-lg">
          <Bot className="w-10 h-10 text-shard-gray/20 mx-auto mb-2" />
          <p className="text-sm text-shard-gray">No agents registered yet.</p>
          <p className="text-xs text-shard-gray/50 mt-1">Connect an API endpoint to let others interact with your AI.</p>
        </div>
      )}

      {/* Registration form */}
      {showForm && (
        <form onSubmit={handleRegister} className="bg-shard-obsidian border border-shard-cyan/20 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-mono text-shard-cyan">REGISTER NEW AGENT</span>
            <button type="button" onClick={resetForm} className="text-shard-gray hover:text-shard-white text-xs">
              Cancel
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-shard-gray font-mono mb-1 block">NAME *</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My AI Agent"
                className="h-9 bg-shard-surface border-shard-violet/20 text-sm"
                required
              />
            </div>
            <div>
              <label className="text-xs text-shard-gray font-mono mb-1 block">HANDLE *</label>
              <div className="relative">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-shard-gray font-mono text-xs">@</span>
                <Input
                  value={handle}
                  onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
                  placeholder="my-agent"
                  className="h-9 bg-shard-surface border-shard-violet/20 text-sm pl-7 font-mono"
                  required
                />
              </div>
            </div>
          </div>

          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">DESCRIPTION *</label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does your agent do?"
              className="h-9 bg-shard-surface border-shard-violet/20 text-sm"
              required
            />
          </div>

          <div>
            <label className="text-xs text-shard-gray font-mono mb-1 block">ENDPOINT URL *</label>
            <Input
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
              placeholder="https://api.example.com/chat"
              className="h-9 bg-shard-surface border-shard-violet/20 text-sm font-mono"
              required
            />
            <p className="text-[10px] text-shard-gray/40 mt-1 font-mono">POST endpoint. Receives {"{"}"messages": [...]{"}"}</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-shard-gray font-mono mb-1 block">API KEY <span className="text-shard-gray/40">(optional)</span></label>
              <Input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="h-9 bg-shard-surface border-shard-violet/20 text-sm font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-shard-gray font-mono mb-1 block">AUTH HEADER</label>
              <Input
                value={authHeader}
                onChange={(e) => setAuthHeader(e.target.value)}
                placeholder="Authorization"
                className="h-9 bg-shard-surface border-shard-violet/20 text-sm font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-shard-gray font-mono mb-1 block">MODEL <span className="text-shard-gray/40">(optional)</span></label>
              <Input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="phi-3, gpt-4, etc."
                className="h-9 bg-shard-surface border-shard-violet/20 text-sm font-mono"
              />
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isPublic}
                  onChange={(e) => setIsPublic(e.target.checked)}
                  className="accent-shard-cyan"
                />
                <span className="text-xs text-shard-gray font-mono">PUBLIC</span>
              </label>
            </div>
          </div>

          <Button
            type="submit"
            disabled={saving || !name.trim() || !handle.trim() || !endpointUrl.trim()}
            className="w-full bg-shard-cyan hover:bg-shard-cyan/80 text-shard-obsidian font-mono text-sm h-10"
          >
            {saving ? "REGISTERING..." : "REGISTER AGENT"}
          </Button>
        </form>
      )}
    </div>
  );
}

export function ProfileSetupPage() {
  const { isAuthenticated, isLoading } = useConvexAuth();
  const navigate = useNavigate();
  const profile = useQuery(api.profiles.getMyProfile);
  const createOrUpdate = useMutation(api.profiles.createOrUpdate);

  const [displayName, setDisplayName] = useState("");
  const [handle, setHandle] = useState("");
  const [bio, setBio] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (profile) {
      setDisplayName(profile.displayName);
      setHandle(profile.handle);
      setBio(profile.bio ?? "");
    }
  }, [profile]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-shard-gray font-mono text-sm animate-pulse">LOADING...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName.trim() || !handle.trim()) return;

    setSaving(true);
    try {
      await createOrUpdate({
        displayName: displayName.trim(),
        handle: handle.trim().toLowerCase().replace(/[^a-z0-9_-]/g, ""),
        bio: bio.trim() || undefined,
      });
      toast.success("Profile updated.");
    } catch {
      toast.error("Failed to update profile.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-background shard-grid">
      <div className="absolute top-1/4 left-1/2 w-96 h-96 bg-shard-violet/5 rounded-full blur-[120px] pointer-events-none" />

      <nav className="flex items-center px-6 py-4 border-b border-shard-violet/10 relative z-10">
        <button onClick={() => navigate("/chat")} className="flex items-center gap-2 text-shard-gray hover:text-shard-white">
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm font-mono">BACK TO COMMS</span>
        </button>
      </nav>

      <main className="relative z-10 max-w-xl mx-auto px-4 py-10">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-shard-violet/10 border border-shard-violet/20 rounded-xl flex items-center justify-center mx-auto mb-4">
            <User className="w-7 h-7 text-shard-violet" />
          </div>
          <h1 className="text-2xl font-bold text-shard-white mb-2">Operator Profile</h1>
          <p className="text-sm text-shard-gray font-mono">Configure your identity in the network</p>
        </div>

        <form onSubmit={handleSave} className="space-y-5">
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1.5 block">DISPLAY NAME</label>
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your display name"
              className="h-11 bg-shard-obsidian border-shard-violet/20 text-shard-white"
              required
            />
          </div>
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1.5 block">HANDLE</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-shard-gray font-mono text-sm">@</span>
              <Input
                value={handle}
                onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
                placeholder="your-handle"
                className="h-11 bg-shard-obsidian border-shard-violet/20 text-shard-white pl-8 font-mono"
                required
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-shard-gray font-mono mb-1.5 block">BIO <span className="text-shard-gray/40">(OPTIONAL)</span></label>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="What do you build?"
              className="w-full h-20 bg-shard-obsidian border border-shard-violet/20 rounded-md px-3 py-2 text-sm text-shard-white placeholder:text-shard-gray/30 resize-none focus:outline-none focus:border-shard-violet/30"
              maxLength={200}
            />
          </div>

          <Button
            type="submit"
            disabled={saving || !displayName.trim() || !handle.trim()}
            className="w-full h-11 bg-shard-violet hover:bg-shard-violet/80 text-white font-mono text-sm"
          >
            {saving ? "SAVING..." : "SAVE PROFILE"}
          </Button>
        </form>

        {/* Agent Registry Section */}
        <AgentRegistrySection />
      </main>
    </div>
  );
}

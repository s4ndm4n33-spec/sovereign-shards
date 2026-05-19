import { useQuery, useMutation } from "convex/react";
import { api } from "../../convex/_generated/api";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Settings,
  Key,
  Brain,
  Shield,
  Save,
  MessageSquare,
  Link2,
  Activity,
  Zap,
  ExternalLink,
  BarChart3,
  Wrench,
  RefreshCw,
} from "lucide-react";

const SETTING_LABELS: Record<string, { label: string; description: string; icon: typeof Key; sensitive?: boolean }> = {
  gemini_api_key: {
    label: "Gemini API Key (Primary)",
    description: "Free key from aistudio.google.com/apikey — 1,500 req/day. Primary provider.",
    icon: Key,
    sensitive: true,
  },
  groq_api_key: {
    label: "Groq API Key (Fallback)",
    description: "Free key from console.groq.com — auto-fallback if Gemini is down",
    icon: Key,
    sensitive: true,
  },
  cerebras_api_key: {
    label: "Cerebras API Key (Fallback)",
    description: "Free key from cerebras.ai — third fallback provider",
    icon: Key,
    sensitive: true,
  },
  github_token: {
    label: "GitHub Token",
    description: "Personal access token for repo operations (read/write/push)",
    icon: Key,
    sensitive: true,
  },
  default_model: {
    label: "Default Model",
    description: "Model ID. Primary: gemini-2.0-flash. Also: gemini-2.0-flash-lite, llama-3.1-8b-instant",
    icon: Brain,
  },
  token_budget: {
    label: "Token Budget",
    description: "Max context window (J's hard cap is 4096)",
    icon: Zap,
  },
  system_prompt_override: {
    label: "System Prompt Override",
    description: "Custom system prompt — leave empty for default J personality",
    icon: MessageSquare,
  },
  github_default_owner: {
    label: "Default GitHub Owner",
    description: "Default owner for repo connections",
    icon: Link2,
  },
  github_default_repo: {
    label: "Default GitHub Repo",
    description: "Default repository name",
    icon: Link2,
  },
  github_default_branch: {
    label: "Default Branch",
    description: "Default branch for repo connections",
    icon: Link2,
  },
  admin_emails: {
    label: "Admin Emails",
    description: "Comma-separated list of admin email addresses",
    icon: Shield,
  },
  maintenance_mode: {
    label: "Maintenance Mode",
    description: "Set to 'true' to disable chat (for maintenance)",
    icon: Wrench,
  },
};

function SettingRow({
  settingKey,
  value,
  onSave,
}: {
  settingKey: string;
  value: string;
  onSave: (key: string, value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const config = SETTING_LABELS[settingKey];

  if (!config) return null;
  const Icon = config.icon;

  return (
    <div className="flex items-start gap-4 py-4">
      <div className="size-9 rounded-lg bg-[#1E90FF]/10 flex items-center justify-center shrink-0 mt-0.5">
        <Icon className="size-4 text-[#1E90FF]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-white">{config.label}</span>
          {config.sensitive && (
            <Badge className="text-[9px] bg-[#FFD700]/15 text-[#FFD700] border-0">Sensitive</Badge>
          )}
        </div>
        <p className="text-[11px] text-[#8888a0] mb-2">{config.description}</p>
        {editing ? (
          <div className="flex gap-2">
            <Input
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              type={config.sensitive ? "password" : "text"}
              className="bg-[#0d0d1a] border-[#1a1a2e] text-white text-xs h-8"
              autoFocus
            />
            <Button
              size="sm"
              onClick={() => {
                // Don't overwrite with empty or masked values
                if (config.sensitive && (!editValue.trim() || editValue.startsWith("••"))) {
                  setEditing(false);
                  return;
                }
                onSave(settingKey, editValue);
                setEditing(false);
              }}
              className="bg-[#1E90FF] hover:bg-[#1E90FF]/80 text-white h-8 px-3"
            >
              <Save className="size-3 mr-1" /> Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditValue(value);
                setEditing(false);
              }}
              className="text-[#8888a0] h-8"
            >
              Cancel
            </Button>
          </div>
        ) : (
          <button
            onClick={() => {
              // For sensitive fields, don't pre-fill masked value — start blank
              setEditValue(config.sensitive ? "" : value);
              setEditing(true);
            }}
            className="text-xs font-mono px-3 py-1.5 rounded bg-[#06060F] border border-[#1a1a2e] text-[#8888a0] hover:text-white hover:border-[#1E90FF]/30 transition text-left w-full truncate"
          >
            {value || "(not set)"}
          </button>
        )}
      </div>
    </div>
  );
}

export function AdminPage() {
  const settings = useQuery(api.admin.getAllSettings) || [];
  const stats = useQuery(api.admin.getStats);
  const setSetting = useMutation(api.admin.setSetting);

  const handleSave = async (key: string, value: string) => {
    await setSetting({ key, value });
  };

  const statItems = [
    { label: "Conversations", value: stats?.totalConversations ?? 0, icon: MessageSquare, color: "text-[#1E90FF]" },
    { label: "Messages", value: stats?.totalMessages ?? 0, icon: BarChart3, color: "text-[#00d4aa]" },
    { label: "Chain Sessions", value: stats?.totalChainSessions ?? 0, icon: Link2, color: "text-[#FFD700]" },
    { label: "Active Chains", value: stats?.activeChains ?? 0, icon: Activity, color: "text-[#00FF41]" },
  ];

  return (
    <div className="h-[calc(100vh-3rem)] md:h-screen bg-[#06060F]">
      <ScrollArea className="h-full">
        <div className="max-w-3xl mx-auto p-6">
          {/* Header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="size-10 rounded-xl bg-gradient-to-br from-[#1E90FF] to-[#00d4aa] flex items-center justify-center">
              <Settings className="size-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Admin Panel</h1>
              <p className="text-xs text-[#8888a0]">Configure J Cloud — model, API keys, maintenance</p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
            {statItems.map((s) => (
              <Card key={s.label} className="bg-[#0a0a14] border-[#1a1a2e]">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <s.icon className={`size-4 ${s.color}`} />
                    <span className="text-[10px] text-[#8888a0] uppercase tracking-wider">{s.label}</span>
                  </div>
                  <span className="text-2xl font-bold text-white">{s.value}</span>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Quick Actions */}
          <Card className="bg-[#0a0a14] border-[#1a1a2e] mb-8">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-white flex items-center gap-2">
                <Zap className="size-4 text-[#FFD700]" />
                Quick Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <a
                href="https://aistudio.google.com/apikey"
                target="_blank"
                rel="noopener"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1a2e] text-xs text-[#8888a0] hover:text-white hover:bg-[#1a1a2e]/80 transition"
              >
                Get Gemini API Key <ExternalLink className="size-3" />
              </a>
              <a
                href="https://console.groq.com"
                target="_blank"
                rel="noopener"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1a2e] text-xs text-[#8888a0] hover:text-white hover:bg-[#1a1a2e]/80 transition"
              >
                Get Groq API Key <ExternalLink className="size-3" />
              </a>
              <a
                href="https://github.com/s4ndm4n33-spec/sovereign-shards"
                target="_blank"
                rel="noopener"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1a2e] text-xs text-[#8888a0] hover:text-white hover:bg-[#1a1a2e]/80 transition"
              >
                GitHub Repo <ExternalLink className="size-3" />
              </a>
              <button
                onClick={() => window.location.reload()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1a2e] text-xs text-[#8888a0] hover:text-white hover:bg-[#1a1a2e]/80 transition"
              >
                <RefreshCw className="size-3" /> Refresh
              </button>
            </CardContent>
          </Card>

          {/* Settings */}
          <Card className="bg-[#0a0a14] border-[#1a1a2e]">
            <CardHeader>
              <CardTitle className="text-sm text-white flex items-center gap-2">
                <Shield className="size-4 text-[#1E90FF]" />
                Configuration
              </CardTitle>
              <CardDescription className="text-[11px] text-[#8888a0]">
                Edit any setting below. Changes take effect immediately.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="divide-y divide-[#1a1a2e]">
                {settings.map((s) => (
                  <SettingRow
                    key={s.key}
                    settingKey={s.key}
                    value={s.value}
                    onSave={handleSave}
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
    </div>
  );
}

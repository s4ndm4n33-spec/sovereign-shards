import { getAuthUserId } from "@convex-dev/auth/server";
import { mutation, query, internalQuery } from "./_generated/server";
import { v } from "convex/values";

// Default settings
const DEFAULTS: Record<string, string> = {
  "gemini_api_key": "",
  "groq_api_key": "",
  "cerebras_api_key": "",
  "default_model": "gemini-2.0-flash",
  "token_budget": "4096",
  "system_prompt_override": "",
  "github_token": "",
  "github_default_owner": "",
  "github_default_repo": "",
  "github_default_branch": "main",
  "admin_emails": "",
  "maintenance_mode": "false",
};

// Keys that should be masked in the UI
const MASKED_KEYS = new Set(["gemini_api_key", "groq_api_key", "cerebras_api_key", "github_token"]);

export const getSetting = query({
  args: { key: v.string() },
  returns: v.union(v.string(), v.null()),
  handler: async (ctx, args) => {
    const row = await ctx.db
      .query("adminSettings")
      .withIndex("by_key", (q) => q.eq("key", args.key))
      .unique();
    return row?.value ?? DEFAULTS[args.key] ?? null;
  },
});

export const getSettingInternal = internalQuery({
  args: { key: v.string() },
  returns: v.union(v.string(), v.null()),
  handler: async (ctx, args) => {
    const row = await ctx.db
      .query("adminSettings")
      .withIndex("by_key", (q) => q.eq("key", args.key))
      .unique();
    return row?.value ?? DEFAULTS[args.key] ?? null;
  },
});

export const getAllSettings = query({
  args: {},
  returns: v.array(v.object({
    key: v.string(),
    value: v.string(),
  })),
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];

    const stored = await ctx.db.query("adminSettings").collect();
    const storedMap = new Map(stored.map((s) => [s.key, s.value]));

    const result: Array<{ key: string; value: string }> = [];
    for (const [key, defaultVal] of Object.entries(DEFAULTS)) {
      // Mask sensitive keys
      let value = storedMap.get(key) ?? defaultVal;
      if (MASKED_KEYS.has(key) && value && value.length > 8) {
        value = value.slice(0, 8) + "…" + value.slice(-4);
      }
      result.push({ key, value });
    }
    return result;
  },
});

export const setSetting = mutation({
  args: {
    key: v.string(),
    value: v.string(),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");

    const existing = await ctx.db
      .query("adminSettings")
      .withIndex("by_key", (q) => q.eq("key", args.key))
      .unique();

    if (existing) {
      await ctx.db.patch(existing._id, { value: args.value, updatedBy: userId });
    } else {
      await ctx.db.insert("adminSettings", {
        key: args.key,
        value: args.value,
        updatedBy: userId,
      });
    }
    return null;
  },
});

export const getStats = query({
  args: {},
  returns: v.object({
    totalConversations: v.number(),
    totalMessages: v.number(),
    totalChainSessions: v.number(),
    activeChains: v.number(),
  }),
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return { totalConversations: 0, totalMessages: 0, totalChainSessions: 0, activeChains: 0 };

    const convos = await ctx.db
      .query("conversations")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .collect();
    let totalMessages = 0;
    for (const c of convos) {
      const msgs = await ctx.db
        .query("messages")
        .withIndex("by_conversation", (q) => q.eq("conversationId", c._id))
        .collect();
      totalMessages += msgs.length;
    }
    const chainLogs = await ctx.db
      .query("chainLogs")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .collect();
    const sessions = new Set(chainLogs.map((l) => l.sessionId));
    const activeChains = chainLogs.filter((l) => l.status === "running").length;

    return {
      totalConversations: convos.length,
      totalMessages,
      totalChainSessions: sessions.size,
      activeChains,
    };
  },
});

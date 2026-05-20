import { v } from "convex/values";
import { mutation, query } from "./_generated/server";
import { J_CONFIG } from "./constants";

// Ensure J exists in the database — called on admin panel load
export const ensureJ = mutation({
  args: {},
  returns: v.null(),
  handler: async (ctx) => {
    const existing = await ctx.db
      .query("systemAI")
      .withIndex("by_handle", (q: any) => q.eq("handle", J_CONFIG.handle))
      .unique();

    if (!existing) {
      await ctx.db.insert("systemAI", {
        handle: J_CONFIG.handle,
        displayName: J_CONFIG.displayName,
        bio: J_CONFIG.bio,
        avatarColor: J_CONFIG.avatarColor,
        tokenBudget: J_CONFIG.tokenBudget,
        geminiModel: J_CONFIG.providers.gemini.defaultModel,
        groqModel: J_CONFIG.providers.groq.defaultModel,
        cerebrasModel: J_CONFIG.providers.cerebras.defaultModel,
        defaultModel: J_CONFIG.providers.gemini.defaultModel,
        isActive: false, // inactive until at least one API key is set
        moderationSensitivity: J_CONFIG.defaultHeuristics.moderationSensitivity,
        responseStyle: J_CONFIG.defaultHeuristics.responseStyle,
        autoModerate: J_CONFIG.defaultHeuristics.autoModerate,
        greetNewUsers: J_CONFIG.defaultHeuristics.greetNewUsers,
        maxResponseLength: J_CONFIG.defaultHeuristics.maxResponseLength,
        personality: J_CONFIG.defaultHeuristics.personality,
        totalInvocations: 0,
      });
    }
    return null;
  },
});

// Get J's config (hides actual key values, exposes booleans)
export const getConfig = query({
  args: {},
  handler: async (ctx) => {
    const j = await ctx.db
      .query("systemAI")
      .withIndex("by_handle", (q: any) => q.eq("handle", J_CONFIG.handle))
      .unique();

    if (!j) return null;

    return {
      _id: j._id,
      handle: j.handle,
      displayName: j.displayName,
      bio: j.bio,
      avatarColor: j.avatarColor,
      // Provider status (keys hidden)
      hasGeminiKey: !!j.geminiApiKey,
      geminiModel: j.geminiModel ?? J_CONFIG.providers.gemini.defaultModel,
      hasGroqKey: !!j.groqApiKey,
      groqModel: j.groqModel ?? J_CONFIG.providers.groq.defaultModel,
      hasCerebrasKey: !!j.cerebrasApiKey,
      cerebrasModel: j.cerebrasModel ?? J_CONFIG.providers.cerebras.defaultModel,
      defaultModel: j.defaultModel ?? J_CONFIG.providers.gemini.defaultModel,
      tokenBudget: j.tokenBudget,
      systemPromptOverride: j.systemPromptOverride,
      isActive: j.isActive,
      // Heuristics
      moderationSensitivity: j.moderationSensitivity,
      responseStyle: j.responseStyle,
      autoModerate: j.autoModerate,
      greetNewUsers: j.greetNewUsers,
      maxResponseLength: j.maxResponseLength,
      personality: j.personality,
      totalInvocations: j.totalInvocations,
      lastActiveAt: j.lastActiveAt,
    };
  },
});

// Update provider keys and models
export const updateProviders = mutation({
  args: {
    geminiApiKey: v.optional(v.string()),
    geminiModel: v.optional(v.string()),
    groqApiKey: v.optional(v.string()),
    groqModel: v.optional(v.string()),
    cerebrasApiKey: v.optional(v.string()),
    cerebrasModel: v.optional(v.string()),
    defaultModel: v.optional(v.string()),
    tokenBudget: v.optional(v.number()),
    systemPromptOverride: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const j = await ctx.db
      .query("systemAI")
      .withIndex("by_handle", (q: any) => q.eq("handle", J_CONFIG.handle))
      .unique();

    if (!j) return { success: false };

    const updates: Record<string, any> = {};
    if (args.geminiApiKey !== undefined) updates.geminiApiKey = args.geminiApiKey;
    if (args.geminiModel !== undefined) updates.geminiModel = args.geminiModel;
    if (args.groqApiKey !== undefined) updates.groqApiKey = args.groqApiKey;
    if (args.groqModel !== undefined) updates.groqModel = args.groqModel;
    if (args.cerebrasApiKey !== undefined) updates.cerebrasApiKey = args.cerebrasApiKey;
    if (args.cerebrasModel !== undefined) updates.cerebrasModel = args.cerebrasModel;
    if (args.defaultModel !== undefined) updates.defaultModel = args.defaultModel;
    if (args.tokenBudget !== undefined) updates.tokenBudget = Math.min(args.tokenBudget, 4096);
    if (args.systemPromptOverride !== undefined) updates.systemPromptOverride = args.systemPromptOverride || undefined;

    // Auto-activate if any key is set
    const hasAnyKey = (args.geminiApiKey || j.geminiApiKey) ||
                      (args.groqApiKey || j.groqApiKey) ||
                      (args.cerebrasApiKey || j.cerebrasApiKey);
    if (hasAnyKey) updates.isActive = true;

    await ctx.db.patch(j._id, updates);
    return { success: true };
  },
});

// Update J's heuristic calibration
export const updateHeuristics = mutation({
  args: {
    moderationSensitivity: v.optional(v.number()),
    responseStyle: v.optional(v.string()),
    autoModerate: v.optional(v.boolean()),
    greetNewUsers: v.optional(v.boolean()),
    maxResponseLength: v.optional(v.number()),
    personality: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const j = await ctx.db
      .query("systemAI")
      .withIndex("by_handle", (q: any) => q.eq("handle", J_CONFIG.handle))
      .unique();

    if (!j) return { success: false };

    const updates: Record<string, any> = {};
    if (args.moderationSensitivity !== undefined) updates.moderationSensitivity = args.moderationSensitivity;
    if (args.responseStyle !== undefined) updates.responseStyle = args.responseStyle;
    if (args.autoModerate !== undefined) updates.autoModerate = args.autoModerate;
    if (args.greetNewUsers !== undefined) updates.greetNewUsers = args.greetNewUsers;
    if (args.maxResponseLength !== undefined) updates.maxResponseLength = args.maxResponseLength;
    if (args.personality !== undefined) updates.personality = args.personality;

    await ctx.db.patch(j._id, updates);
    return { success: true };
  },
});

// Update J's profile info
export const updateProfile = mutation({
  args: {
    displayName: v.optional(v.string()),
    bio: v.optional(v.string()),
    avatarColor: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const j = await ctx.db
      .query("systemAI")
      .withIndex("by_handle", (q: any) => q.eq("handle", J_CONFIG.handle))
      .unique();

    if (!j) return { success: false };

    const updates: Record<string, any> = {};
    if (args.displayName !== undefined) updates.displayName = args.displayName;
    if (args.bio !== undefined) updates.bio = args.bio;
    if (args.avatarColor !== undefined) updates.avatarColor = args.avatarColor;

    await ctx.db.patch(j._id, updates);
    return { success: true };
  },
});

// Toggle J active/inactive
export const setActive = mutation({
  args: { isActive: v.boolean() },
  handler: async (ctx, args) => {
    const j = await ctx.db
      .query("systemAI")
      .withIndex("by_handle", (q: any) => q.eq("handle", J_CONFIG.handle))
      .unique();

    if (!j) return { success: false };
    await ctx.db.patch(j._id, { isActive: args.isActive });
    return { success: true };
  },
});

// Get J's public-facing info for chat display (no secrets)
export const getPublicInfo = query({
  args: {},
  handler: async (ctx) => {
    const j = await ctx.db
      .query("systemAI")
      .withIndex("by_handle", (q: any) => q.eq("handle", J_CONFIG.handle))
      .unique();

    if (!j) return null;

    return {
      handle: j.handle,
      displayName: j.displayName,
      bio: j.bio,
      avatarColor: j.avatarColor,
      isActive: j.isActive,
      defaultModel: j.defaultModel,
    };
  },
});

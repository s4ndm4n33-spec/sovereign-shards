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
        isActive: false, // inactive until API keys are set
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

// Get J's config
export const getConfig = query({
  args: {},
  returns: v.union(
    v.object({
      _id: v.id("systemAI"),
      handle: v.string(),
      displayName: v.string(),
      bio: v.string(),
      avatarColor: v.string(),
      endpointUrl: v.optional(v.string()),
      hasApiKey: v.boolean(),
      authHeader: v.optional(v.string()),
      model: v.optional(v.string()),
      isActive: v.boolean(),
      moderationSensitivity: v.number(),
      responseStyle: v.string(),
      autoModerate: v.boolean(),
      greetNewUsers: v.boolean(),
      maxResponseLength: v.number(),
      personality: v.string(),
      totalInvocations: v.number(),
      lastActiveAt: v.optional(v.number()),
    }),
    v.null(),
  ),
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
      endpointUrl: j.endpointUrl,
      hasApiKey: !!j.apiKey,
      authHeader: j.authHeader,
      model: j.model,
      isActive: j.isActive,
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

// Update J's API connection
export const updateConnection = mutation({
  args: {
    endpointUrl: v.optional(v.string()),
    apiKey: v.optional(v.string()),
    authHeader: v.optional(v.string()),
    model: v.optional(v.string()),
  },
  returns: v.object({ success: v.boolean() }),
  handler: async (ctx, args) => {
    const j = await ctx.db
      .query("systemAI")
      .withIndex("by_handle", (q: any) => q.eq("handle", J_CONFIG.handle))
      .unique();

    if (!j) return { success: false };

    const updates: Record<string, any> = {};
    if (args.endpointUrl !== undefined) updates.endpointUrl = args.endpointUrl;
    if (args.apiKey !== undefined) updates.apiKey = args.apiKey;
    if (args.authHeader !== undefined) updates.authHeader = args.authHeader;
    if (args.model !== undefined) updates.model = args.model;

    // Auto-activate if endpoint and key are provided
    if (args.endpointUrl && args.apiKey) {
      updates.isActive = true;
    }

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
  returns: v.object({ success: v.boolean() }),
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
  returns: v.object({ success: v.boolean() }),
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
  returns: v.object({ success: v.boolean() }),
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
  returns: v.union(
    v.object({
      handle: v.string(),
      displayName: v.string(),
      bio: v.string(),
      avatarColor: v.string(),
      isActive: v.boolean(),
      model: v.optional(v.string()),
    }),
    v.null(),
  ),
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
      model: j.model,
    };
  },
});

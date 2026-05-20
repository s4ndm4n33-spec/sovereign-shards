import { getAuthUserId } from "@convex-dev/auth/server";
import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

const AVATAR_COLORS = [
  "#6E4BFF", // Sovereign Violet
  "#00D9FF", // Signal Cyan
  "#FFB347", // Warning Amber
  "#4ADE80", // Archive Green
  "#FF4D6D", // Critical Red
  "#7D8597", // Alloy Gray
  "#A78BFA", // Light violet
  "#22D3EE", // Cyan
  "#FB923C", // Orange
  "#34D399", // Emerald
];

export const getMyProfile = query({
  args: {},
  returns: v.union(
    v.object({
      _id: v.id("profiles"),
      _creationTime: v.number(),
      userId: v.id("users"),
      displayName: v.string(),
      handle: v.string(),
      bio: v.optional(v.string()),
      avatarColor: v.string(),
      role: v.union(
        v.literal("user"),
        v.literal("admin"),
        v.literal("moderator"),
      ),
      isBanned: v.boolean(),
      banReason: v.optional(v.string()),
    }),
    v.null(),
  ),
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return null;
    return await ctx.db
      .query("profiles")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .unique();
  },
});

export const getByUserId = query({
  args: { userId: v.id("users") },
  returns: v.union(
    v.object({
      _id: v.id("profiles"),
      _creationTime: v.number(),
      userId: v.id("users"),
      displayName: v.string(),
      handle: v.string(),
      bio: v.optional(v.string()),
      avatarColor: v.string(),
      role: v.union(
        v.literal("user"),
        v.literal("admin"),
        v.literal("moderator"),
      ),
      isBanned: v.boolean(),
      banReason: v.optional(v.string()),
    }),
    v.null(),
  ),
  handler: async (ctx, args) => {
    return await ctx.db
      .query("profiles")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .unique();
  },
});

export const createOrUpdate = mutation({
  args: {
    displayName: v.string(),
    handle: v.string(),
    bio: v.optional(v.string()),
  },
  returns: v.id("profiles"),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");

    const existing = await ctx.db
      .query("profiles")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .unique();

    if (existing) {
      await ctx.db.patch(existing._id, {
        displayName: args.displayName,
        handle: args.handle,
        bio: args.bio,
      });
      return existing._id;
    }

    const color = AVATAR_COLORS[Math.floor(Math.random() * AVATAR_COLORS.length)];

    return await ctx.db.insert("profiles", {
      userId,
      displayName: args.displayName,
      handle: args.handle,
      bio: args.bio,
      avatarColor: color,
      role: "user",
      isBanned: false,
    });
  },
});

// Auto-create profile on first message if they have a user account
export const ensureProfile = mutation({
  args: {},
  returns: v.union(
    v.object({
      _id: v.id("profiles"),
      displayName: v.string(),
      handle: v.string(),
      avatarColor: v.string(),
      role: v.union(
        v.literal("user"),
        v.literal("admin"),
        v.literal("moderator"),
      ),
    }),
    v.null(),
  ),
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return null;

    const existing = await ctx.db
      .query("profiles")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .unique();

    if (existing) {
      return {
        _id: existing._id,
        displayName: existing.displayName,
        handle: existing.handle,
        avatarColor: existing.avatarColor,
        role: existing.role,
      };
    }

    // Get user record for name
    const user = await ctx.db.get(userId);
    const name = (user as { name?: string })?.name ?? "Operator";
    const handle = name.toLowerCase().replace(/[^a-z0-9]/g, "") + Math.floor(Math.random() * 1000);
    const color = AVATAR_COLORS[Math.floor(Math.random() * AVATAR_COLORS.length)];

    const profileId = await ctx.db.insert("profiles", {
      userId,
      displayName: name,
      handle,
      bio: undefined,
      avatarColor: color,
      role: "user",
      isBanned: false,
    });

    return {
      _id: profileId,
      displayName: name,
      handle,
      avatarColor: color,
      role: "user" as const,
    };
  },
});

// Admin: list all profiles
export const listAll = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("profiles"),
      _creationTime: v.number(),
      userId: v.id("users"),
      displayName: v.string(),
      handle: v.string(),
      bio: v.optional(v.string()),
      avatarColor: v.string(),
      role: v.union(
        v.literal("user"),
        v.literal("admin"),
        v.literal("moderator"),
      ),
      isBanned: v.boolean(),
      banReason: v.optional(v.string()),
    }),
  ),
  handler: async (ctx) => {
    return await ctx.db.query("profiles").collect();
  },
});

// Admin: ban/unban user
export const setBanned = mutation({
  args: {
    profileId: v.id("profiles"),
    isBanned: v.boolean(),
    banReason: v.optional(v.string()),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    await ctx.db.patch(args.profileId, {
      isBanned: args.isBanned,
      banReason: args.banReason,
    });
    return null;
  },
});

// Admin: set role
export const setRole = mutation({
  args: {
    profileId: v.id("profiles"),
    role: v.union(
      v.literal("user"),
      v.literal("admin"),
      v.literal("moderator"),
    ),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    await ctx.db.patch(args.profileId, { role: args.role });
    return null;
  },
});

import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

declare const process: { env: Record<string, string | undefined> };

// Admin auth - separate from regular user auth
// Uses username/password stored in env vars
export const login = mutation({
  args: {
    username: v.string(),
    password: v.string(),
  },
  returns: v.object({
    success: v.boolean(),
    token: v.optional(v.string()),
    error: v.optional(v.string()),
  }),
  handler: async (ctx, args) => {
    const adminUsername = process.env.ADMIN_USERNAME;
    const adminPassword = process.env.ADMIN_PASSWORD;

    if (!adminUsername || !adminPassword) {
      return { success: false, error: "Admin not configured." };
    }

    if (args.username !== adminUsername || args.password !== adminPassword) {
      return { success: false, error: "Invalid credentials." };
    }

    // Generate session token
    const token = generateToken();
    const expiresAt = Date.now() + 24 * 60 * 60 * 1000; // 24 hours

    await ctx.db.insert("adminSessions", { token, expiresAt });

    return { success: true, token };
  },
});

export const validateSession = query({
  args: { token: v.string() },
  returns: v.boolean(),
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("adminSessions")
      .withIndex("by_token", (q) => q.eq("token", args.token))
      .unique();

    if (!session) return false;
    if (session.expiresAt < Date.now()) return false;
    return true;
  },
});

export const logout = mutation({
  args: { token: v.string() },
  returns: v.null(),
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("adminSessions")
      .withIndex("by_token", (q) => q.eq("token", args.token))
      .unique();

    if (session) {
      await ctx.db.delete(session._id);
    }
    return null;
  },
});

// Stats for admin dashboard
export const getStats = query({
  args: {},
  returns: v.object({
    totalMessages: v.number(),
    moderatedMessages: v.number(),
    pendingAppeals: v.number(),
    totalUsers: v.number(),
    bannedUsers: v.number(),
    totalRooms: v.number(),
  }),
  handler: async (ctx) => {
    const messages = await ctx.db.query("messages").collect();
    const profiles = await ctx.db.query("profiles").collect();
    const appeals = await ctx.db
      .query("appeals")
      .withIndex("by_status", (q) => q.eq("status", "pending"))
      .collect();
    const rooms = await ctx.db.query("rooms").collect();

    return {
      totalMessages: messages.length,
      moderatedMessages: messages.filter((m) => m.isModerated).length,
      pendingAppeals: appeals.length,
      totalUsers: profiles.length,
      bannedUsers: profiles.filter((p) => p.isBanned).length,
      totalRooms: rooms.length,
    };
  },
});

function generateToken(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 64; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

import { v } from "convex/values";
import { mutation, query } from "./_generated/server";
import { DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD } from "./constants";

// Simple hash for admin passwords (not bcrypt — this is an internal admin panel)
function simpleHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const chr = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + chr;
    hash |= 0;
  }
  // Return hex + length-based salt to reduce collisions
  return `sh_${(hash >>> 0).toString(16)}_${str.length}`;
}

function generateToken(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 64; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

// Auto-seed the super admin on first login if no admin accounts exist
async function ensureSuperAdmin(ctx: any) {
  const existing = await ctx.db.query("adminAccounts").first();
  if (!existing) {
    await ctx.db.insert("adminAccounts", {
      username: DEFAULT_ADMIN_USERNAME,
      passwordHash: simpleHash(DEFAULT_ADMIN_PASSWORD),
      displayName: "S4ndm4n",
      email: "s4ndm4n33@gmail.com",
      role: "super_admin" as const,
      isActive: true,
      lastLoginAt: Date.now(),
    });
  }
}

// Admin auth — checks database accounts, falls back to env/constants for bootstrap
export const login = mutation({
  args: {
    username: v.string(),
    password: v.string(),
  },
  returns: v.object({
    success: v.boolean(),
    token: v.optional(v.string()),
    error: v.optional(v.string()),
    account: v.optional(
      v.object({
        id: v.string(),
        username: v.string(),
        displayName: v.string(),
        role: v.string(),
      })
    ),
  }),
  handler: async (ctx, args) => {
    // Ensure super admin exists
    await ensureSuperAdmin(ctx);

    // Look up in database
    const account = await ctx.db
      .query("adminAccounts")
      .withIndex("by_username", (q: any) => q.eq("username", args.username))
      .unique();

    if (account) {
      if (!account.isActive) {
        return { success: false, error: "Account deactivated." };
      }
      if (account.passwordHash !== simpleHash(args.password)) {
        return { success: false, error: "Invalid credentials." };
      }

      // Update last login
      await ctx.db.patch(account._id, { lastLoginAt: Date.now() });

      // Create session
      const token = generateToken();
      const expiresAt = Date.now() + 24 * 60 * 60 * 1000;
      await ctx.db.insert("adminSessions", { token, adminAccountId: account._id, expiresAt });

      return {
        success: true,
        token,
        account: {
          id: account._id,
          username: account.username,
          displayName: account.displayName,
          role: account.role,
        },
      };
    }

    return { success: false, error: "Invalid credentials." };
  },
});

export const validateSession = query({
  args: { token: v.string() },
  returns: v.object({
    valid: v.boolean(),
    account: v.optional(
      v.object({
        id: v.string(),
        username: v.string(),
        displayName: v.string(),
        role: v.string(),
      })
    ),
  }),
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("adminSessions")
      .withIndex("by_token", (q) => q.eq("token", args.token))
      .unique();

    if (!session) return { valid: false };
    if (session.expiresAt < Date.now()) return { valid: false };

    if (session.adminAccountId) {
      const account = await ctx.db.get(session.adminAccountId);
      if (!account || !account.isActive) return { valid: false };
      return {
        valid: true,
        account: {
          id: account._id,
          username: account.username,
          displayName: account.displayName,
          role: account.role,
        },
      };
    }

    // Legacy session without account link
    return { valid: true };
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

// === Admin Account Management ===

export const listAccounts = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("adminAccounts"),
      username: v.string(),
      displayName: v.string(),
      email: v.optional(v.string()),
      role: v.string(),
      isActive: v.boolean(),
      lastLoginAt: v.optional(v.number()),
      _creationTime: v.number(),
    })
  ),
  handler: async (ctx) => {
    const accounts = await ctx.db.query("adminAccounts").collect();
    return accounts.map((a) => ({
      _id: a._id,
      username: a.username,
      displayName: a.displayName,
      email: a.email,
      role: a.role,
      isActive: a.isActive,
      lastLoginAt: a.lastLoginAt,
      _creationTime: a._creationTime,
    }));
  },
});

export const createAccount = mutation({
  args: {
    username: v.string(),
    password: v.string(),
    displayName: v.string(),
    email: v.optional(v.string()),
    role: v.union(v.literal("super_admin"), v.literal("admin"), v.literal("moderator")),
  },
  returns: v.object({
    success: v.boolean(),
    error: v.optional(v.string()),
  }),
  handler: async (ctx, args) => {
    // Check for duplicate username
    const existing = await ctx.db
      .query("adminAccounts")
      .withIndex("by_username", (q: any) => q.eq("username", args.username))
      .unique();

    if (existing) {
      return { success: false, error: "Username already exists." };
    }

    await ctx.db.insert("adminAccounts", {
      username: args.username,
      passwordHash: simpleHash(args.password),
      displayName: args.displayName,
      email: args.email,
      role: args.role,
      isActive: true,
    });

    return { success: true };
  },
});

export const updateAccount = mutation({
  args: {
    accountId: v.id("adminAccounts"),
    displayName: v.optional(v.string()),
    email: v.optional(v.string()),
    role: v.optional(v.union(v.literal("super_admin"), v.literal("admin"), v.literal("moderator"))),
    isActive: v.optional(v.boolean()),
    newPassword: v.optional(v.string()),
  },
  returns: v.object({
    success: v.boolean(),
    error: v.optional(v.string()),
  }),
  handler: async (ctx, args) => {
    const account = await ctx.db.get(args.accountId);
    if (!account) return { success: false, error: "Account not found." };

    const updates: Record<string, any> = {};
    if (args.displayName !== undefined) updates.displayName = args.displayName;
    if (args.email !== undefined) updates.email = args.email;
    if (args.role !== undefined) updates.role = args.role;
    if (args.isActive !== undefined) updates.isActive = args.isActive;
    if (args.newPassword !== undefined) updates.passwordHash = simpleHash(args.newPassword);

    await ctx.db.patch(args.accountId, updates);
    return { success: true };
  },
});

export const deleteAccount = mutation({
  args: { accountId: v.id("adminAccounts") },
  returns: v.object({
    success: v.boolean(),
    error: v.optional(v.string()),
  }),
  handler: async (ctx, args) => {
    const account = await ctx.db.get(args.accountId);
    if (!account) return { success: false, error: "Account not found." };

    // Don't allow deleting the last super_admin
    if (account.role === "super_admin") {
      const supers = await ctx.db
        .query("adminAccounts")
        .withIndex("by_role", (q: any) => q.eq("role", "super_admin"))
        .collect();
      if (supers.length <= 1) {
        return { success: false, error: "Cannot delete the last super admin." };
      }
    }

    await ctx.db.delete(args.accountId);
    return { success: true };
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
    totalAdmins: v.number(),
  }),
  handler: async (ctx) => {
    const messages = await ctx.db.query("messages").collect();
    const profiles = await ctx.db.query("profiles").collect();
    const appeals = await ctx.db
      .query("appeals")
      .withIndex("by_status", (q) => q.eq("status", "pending"))
      .collect();
    const rooms = await ctx.db.query("rooms").collect();
    const admins = await ctx.db.query("adminAccounts").collect();

    return {
      totalMessages: messages.length,
      moderatedMessages: messages.filter((m) => m.isModerated).length,
      pendingAppeals: appeals.length,
      totalUsers: profiles.length,
      bannedUsers: profiles.filter((p) => p.isBanned).length,
      totalRooms: rooms.length,
      totalAdmins: admins.filter((a) => a.isActive).length,
    };
  },
});

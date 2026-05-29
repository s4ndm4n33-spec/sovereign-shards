import { getAuthUserId } from "@convex-dev/auth/server";
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const list = query({
  args: {
    sessionId: v.optional(v.string()),
    status: v.optional(v.union(v.literal("running"), v.literal("done"), v.literal("error"), v.literal("paused"))),
  },
  returns: v.array(v.object({
    _id: v.id("chainLogs"),
    _creationTime: v.number(),
    sessionId: v.string(),
    phase: v.string(),
    step: v.number(),
    action: v.string(),
    input: v.optional(v.string()),
    output: v.optional(v.string()),
    status: v.union(v.literal("running"), v.literal("done"), v.literal("error"), v.literal("paused")),
    parentId: v.optional(v.id("chainLogs")),
  })),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];

    if (args.sessionId) {
      return await ctx.db
        .query("chainLogs")
        .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId!))
        .order("asc")
        .collect();
    }

    if (args.status) {
      return await ctx.db
        .query("chainLogs")
        .withIndex("by_status", (q) => q.eq("status", args.status!))
        .order("desc")
        .take(100);
    }

    return await ctx.db
      .query("chainLogs")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .order("desc")
      .take(100);
  },
});

export const sessions = query({
  args: {},
  returns: v.array(v.object({
    sessionId: v.string(),
    phase: v.string(),
    steps: v.number(),
    status: v.union(v.literal("running"), v.literal("done"), v.literal("error"), v.literal("paused")),
    lastActivity: v.number(),
  })),
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];
    const logs = await ctx.db
      .query("chainLogs")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .order("desc")
      .take(500);

    // Group by session
    const sessionMap = new Map<string, {
      phase: string;
      steps: number;
      status: "running" | "done" | "error" | "paused";
      lastActivity: number;
    }>();
    for (const log of logs) {
      const existing = sessionMap.get(log.sessionId);
      if (!existing) {
        sessionMap.set(log.sessionId, {
          phase: log.phase,
          steps: 1,
          status: log.status,
          lastActivity: log._creationTime,
        });
      } else {
        existing.steps++;
        if (log._creationTime > existing.lastActivity) {
          existing.lastActivity = log._creationTime;
          existing.phase = log.phase;
          existing.status = log.status;
        }
      }
    }

    return Array.from(sessionMap.entries()).map(([sessionId, data]) => ({
      sessionId,
      ...data,
    }));
  },
});

export const create = mutation({
  args: {
    sessionId: v.string(),
    phase: v.string(),
    step: v.number(),
    action: v.string(),
    input: v.optional(v.string()),
    status: v.union(v.literal("running"), v.literal("done"), v.literal("error"), v.literal("paused")),
  },
  returns: v.id("chainLogs"),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    return await ctx.db.insert("chainLogs", {
      userId,
      ...args,
    });
  },
});

export const updateStatus = mutation({
  args: {
    id: v.id("chainLogs"),
    status: v.union(v.literal("running"), v.literal("done"), v.literal("error"), v.literal("paused")),
    output: v.optional(v.string()),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    const updates: Record<string, unknown> = { status: args.status };
    if (args.output !== undefined) updates.output = args.output;
    await ctx.db.patch(args.id, updates);
    return null;
  },
});

export const clearSession = mutation({
  args: { sessionId: v.string() },
  returns: v.null(),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    const logs = await ctx.db
      .query("chainLogs")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .collect();
    for (const log of logs) {
      await ctx.db.delete(log._id);
    }
    return null;
  },
});

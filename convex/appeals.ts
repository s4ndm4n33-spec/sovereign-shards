import { getAuthUserId } from "@convex-dev/auth/server";
import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const submit = mutation({
  args: {
    messageId: v.id("messages"),
    reason: v.string(),
    anonymousId: v.optional(v.string()),
  },
  returns: v.object({
    success: v.boolean(),
    error: v.optional(v.string()),
  }),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);

    // Check for duplicate appeal
    const existing = await ctx.db
      .query("appeals")
      .withIndex("by_message", (q) => q.eq("messageId", args.messageId))
      .collect();

    const hasDuplicate = existing.some((a) => {
      if (userId) return a.userId === userId;
      return a.anonymousId === args.anonymousId;
    });

    if (hasDuplicate) {
      return { success: false, error: "You have already submitted an appeal for this message." };
    }

    await ctx.db.insert("appeals", {
      messageId: args.messageId,
      userId: userId ?? undefined,
      anonymousId: userId ? undefined : args.anonymousId,
      reason: args.reason,
      status: "pending",
    });

    return { success: true };
  },
});

export const listPending = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("appeals"),
      _creationTime: v.number(),
      messageId: v.id("messages"),
      userId: v.optional(v.id("users")),
      anonymousId: v.optional(v.string()),
      reason: v.string(),
      status: v.union(
        v.literal("pending"),
        v.literal("approved"),
        v.literal("rejected"),
      ),
      adminResponse: v.optional(v.string()),
      messageContent: v.optional(v.string()),
      messageRoom: v.optional(v.string()),
    }),
  ),
  handler: async (ctx) => {
    const appeals = await ctx.db
      .query("appeals")
      .withIndex("by_status", (q) => q.eq("status", "pending"))
      .collect();

    const result = [];
    for (const appeal of appeals) {
      const message = await ctx.db.get(appeal.messageId);
      const room = message ? await ctx.db.get(message.roomId) : null;
      result.push({
        ...appeal,
        messageContent: message?.content,
        messageRoom: room?.name,
      });
    }
    return result;
  },
});

export const listAll = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("appeals"),
      _creationTime: v.number(),
      messageId: v.id("messages"),
      userId: v.optional(v.id("users")),
      anonymousId: v.optional(v.string()),
      reason: v.string(),
      status: v.union(
        v.literal("pending"),
        v.literal("approved"),
        v.literal("rejected"),
      ),
      adminResponse: v.optional(v.string()),
      messageContent: v.optional(v.string()),
      messageRoom: v.optional(v.string()),
    }),
  ),
  handler: async (ctx) => {
    const appeals = await ctx.db
      .query("appeals")
      .order("desc")
      .take(100);

    const result = [];
    for (const appeal of appeals) {
      const message = await ctx.db.get(appeal.messageId);
      const room = message ? await ctx.db.get(message.roomId) : null;
      result.push({
        ...appeal,
        messageContent: message?.content,
        messageRoom: room?.name,
      });
    }
    return result;
  },
});

export const resolve = mutation({
  args: {
    appealId: v.id("appeals"),
    status: v.union(v.literal("approved"), v.literal("rejected")),
    adminResponse: v.optional(v.string()),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);

    await ctx.db.patch(args.appealId, {
      status: args.status,
      adminResponse: args.adminResponse,
      adminId: userId ?? undefined,
    });

    // If approved, restore the message
    if (args.status === "approved") {
      const appeal = await ctx.db.get(args.appealId);
      if (appeal) {
        await ctx.db.patch(appeal.messageId, {
          isModerated: false,
          moderationReason: undefined,
        });
      }
    }

    return null;
  },
});

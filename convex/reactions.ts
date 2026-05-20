import { getAuthUserId } from "@convex-dev/auth/server";
import { v } from "convex/values";
import { mutation } from "./_generated/server";

export const toggle = mutation({
  args: {
    messageId: v.id("messages"),
    emoji: v.string(),
    anonymousId: v.optional(v.string()),
  },
  returns: v.union(v.literal("added"), v.literal("removed")),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);

    // Find existing reaction from this user
    const allReactions = await ctx.db
      .query("reactions")
      .withIndex("by_message", (q) => q.eq("messageId", args.messageId))
      .collect();

    const existing = allReactions.find((r) => {
      if (r.emoji !== args.emoji) return false;
      if (userId) return r.userId === userId;
      return r.anonymousId === args.anonymousId;
    });

    if (existing) {
      await ctx.db.delete(existing._id);
      return "removed";
    }

    await ctx.db.insert("reactions", {
      messageId: args.messageId,
      userId: userId ?? undefined,
      anonymousId: userId ? undefined : args.anonymousId,
      emoji: args.emoji,
    });
    return "added";
  },
});

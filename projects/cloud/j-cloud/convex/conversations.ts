import { getAuthUserId } from "@convex-dev/auth/server";
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const list = query({
  args: { archived: v.optional(v.boolean()) },
  returns: v.array(v.object({
    _id: v.id("conversations"),
    _creationTime: v.number(),
    title: v.string(),
    model: v.string(),
    tokenBudget: v.number(),
    archived: v.boolean(),
    lastMessage: v.optional(v.string()),
  })),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];
    const archived = args.archived ?? false;
    const convos = await ctx.db
      .query("conversations")
      .withIndex("by_user_archived", (q) => q.eq("userId", userId).eq("archived", archived))
      .order("desc")
      .collect();

    const results = [];
    for (const c of convos) {
      const lastMsg = await ctx.db
        .query("messages")
        .withIndex("by_conversation", (q) => q.eq("conversationId", c._id))
        .order("desc")
        .first();
      results.push({
        _id: c._id,
        _creationTime: c._creationTime,
        title: c.title,
        model: c.model,
        tokenBudget: c.tokenBudget,
        archived: c.archived,
        lastMessage: lastMsg?.content?.slice(0, 100),
      });
    }
    return results;
  },
});

export const create = mutation({
  args: {
    title: v.optional(v.string()),
    model: v.optional(v.string()),
  },
  returns: v.id("conversations"),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    return await ctx.db.insert("conversations", {
      userId,
      title: args.title || "New Conversation",
      model: args.model || "llama-3.1-8b-instant",
      tokenBudget: 4096,
      archived: false,
    });
  },
});

export const update = mutation({
  args: {
    id: v.id("conversations"),
    title: v.optional(v.string()),
    archived: v.optional(v.boolean()),
    model: v.optional(v.string()),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    const convo = await ctx.db.get(args.id);
    if (!convo || convo.userId !== userId) throw new Error("Not found");
    const updates: Record<string, unknown> = {};
    if (args.title !== undefined) updates.title = args.title;
    if (args.archived !== undefined) updates.archived = args.archived;
    if (args.model !== undefined) updates.model = args.model;
    await ctx.db.patch(args.id, updates);
    return null;
  },
});

export const remove = mutation({
  args: { id: v.id("conversations") },
  returns: v.null(),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    const convo = await ctx.db.get(args.id);
    if (!convo || convo.userId !== userId) throw new Error("Not found");
    // Delete all messages first
    const msgs = await ctx.db
      .query("messages")
      .withIndex("by_conversation", (q) => q.eq("conversationId", args.id))
      .collect();
    for (const msg of msgs) {
      await ctx.db.delete(msg._id);
    }
    await ctx.db.delete(args.id);
    return null;
  },
});

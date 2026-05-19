import { getAuthUserId } from "@convex-dev/auth/server";
import { mutation, query, internalQuery, internalMutation } from "./_generated/server";
import { v } from "convex/values";

const toolCallValidator = v.object({
  tool: v.string(),
  args: v.string(),
  result: v.optional(v.string()),
  status: v.union(v.literal("pending"), v.literal("success"), v.literal("error")),
});

const metadataValidator = v.object({
  model: v.optional(v.string()),
  latencyMs: v.optional(v.number()),
  tokensUsed: v.optional(v.number()),
});

export const list = query({
  args: { conversationId: v.id("conversations") },
  returns: v.array(v.object({
    _id: v.id("messages"),
    _creationTime: v.number(),
    conversationId: v.id("conversations"),
    role: v.union(v.literal("user"), v.literal("assistant"), v.literal("system")),
    content: v.string(),
    tokenCount: v.optional(v.number()),
    toolCalls: v.optional(v.array(toolCallValidator)),
    metadata: v.optional(metadataValidator),
  })),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];
    // Verify ownership
    const convo = await ctx.db.get(args.conversationId);
    if (!convo || convo.userId !== userId) return [];
    return await ctx.db
      .query("messages")
      .withIndex("by_conversation", (q) => q.eq("conversationId", args.conversationId))
      .order("asc")
      .collect();
  },
});

export const send = mutation({
  args: {
    conversationId: v.id("conversations"),
    content: v.string(),
  },
  returns: v.id("messages"),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    const convo = await ctx.db.get(args.conversationId);
    if (!convo || convo.userId !== userId) throw new Error("Not found");

    // Simple token estimate (~4 chars per token)
    const tokenCount = Math.ceil(args.content.length / 4);

    const msgId = await ctx.db.insert("messages", {
      conversationId: args.conversationId,
      role: "user",
      content: args.content,
      tokenCount,
    });

    // Auto-update title from first message
    const allMsgs = await ctx.db
      .query("messages")
      .withIndex("by_conversation", (q) => q.eq("conversationId", args.conversationId))
      .collect();
    if (allMsgs.length === 1) {
      await ctx.db.patch(args.conversationId, {
        title: args.content.slice(0, 60) + (args.content.length > 60 ? "…" : ""),
      });
    }

    return msgId;
  },
});

export const addAssistantMessage = mutation({
  args: {
    conversationId: v.id("conversations"),
    content: v.string(),
    toolCalls: v.optional(v.array(toolCallValidator)),
    metadata: v.optional(metadataValidator),
  },
  returns: v.id("messages"),
  handler: async (ctx, args) => {
    const tokenCount = Math.ceil(args.content.length / 4);
    return await ctx.db.insert("messages", {
      conversationId: args.conversationId,
      role: "assistant",
      content: args.content,
      tokenCount,
      toolCalls: args.toolCalls,
      metadata: args.metadata,
    });
  },
});

// Internal versions for actions
export const listInternal = internalQuery({
  args: { conversationId: v.id("conversations") },
  returns: v.array(v.object({
    _id: v.id("messages"),
    _creationTime: v.number(),
    conversationId: v.id("conversations"),
    role: v.union(v.literal("user"), v.literal("assistant"), v.literal("system")),
    content: v.string(),
    tokenCount: v.optional(v.number()),
    toolCalls: v.optional(v.array(toolCallValidator)),
    metadata: v.optional(metadataValidator),
  })),
  handler: async (ctx, args) => {
    return await ctx.db
      .query("messages")
      .withIndex("by_conversation", (q) => q.eq("conversationId", args.conversationId))
      .order("asc")
      .collect();
  },
});

export const addAssistantMessageInternal = internalMutation({
  args: {
    conversationId: v.id("conversations"),
    content: v.string(),
    toolCalls: v.optional(v.array(toolCallValidator)),
    metadata: v.optional(metadataValidator),
  },
  returns: v.id("messages"),
  handler: async (ctx, args) => {
    const tokenCount = Math.ceil(args.content.length / 4);
    return await ctx.db.insert("messages", {
      conversationId: args.conversationId,
      role: "assistant",
      content: args.content,
      tokenCount,
      toolCalls: args.toolCalls,
      metadata: args.metadata,
    });
  },
});

import { getAuthUserId } from "@convex-dev/auth/server";
import { v } from "convex/values";
import type { Id } from "./_generated/dataModel";
import { mutation, query } from "./_generated/server";
import { internal } from "./_generated/api";
import { moderateContent } from "./moderation";
import { J_CONFIG } from "./constants";

export const list = query({
  args: {
    roomId: v.id("rooms"),
    limit: v.optional(v.number()),
  },
  returns: v.array(
    v.object({
      _id: v.id("messages"),
      _creationTime: v.number(),
      roomId: v.id("rooms"),
      userId: v.optional(v.id("users")),
      anonymousName: v.optional(v.string()),
      anonymousId: v.optional(v.string()),
      content: v.string(),
      messageType: v.union(
        v.literal("text"),
        v.literal("code"),
        v.literal("image"),
      ),
      codeLanguage: v.optional(v.string()),
      isModerated: v.boolean(),
      moderationReason: v.optional(v.string()),
      isDeleted: v.boolean(),
      isSystemAI: v.optional(v.boolean()),
      agentHandle: v.optional(v.string()),
      profile: v.union(
        v.object({
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
      reactions: v.array(
        v.object({
          emoji: v.string(),
          count: v.number(),
          userIds: v.array(v.union(v.id("users"), v.null())),
          anonymousIds: v.array(v.union(v.string(), v.null())),
        }),
      ),
    }),
  ),
  handler: async (ctx, args) => {
    const limit = args.limit ?? 100;
    const messages = await ctx.db
      .query("messages")
      .withIndex("by_room", (q) => q.eq("roomId", args.roomId))
      .order("desc")
      .take(limit);

    // Reverse to get chronological order
    messages.reverse();

    const result = [];
    for (const msg of messages) {
      // Get profile if user-sent message
      let profile = null;
      if (msg.userId) {
        const p = await ctx.db
          .query("profiles")
          .withIndex("by_userId", (q) => q.eq("userId", msg.userId!))
          .unique();
        if (p) {
          profile = {
            displayName: p.displayName,
            handle: p.handle,
            avatarColor: p.avatarColor,
            role: p.role,
          };
        }
      }

      // Get reactions grouped by emoji
      const allReactions = await ctx.db
        .query("reactions")
        .withIndex("by_message", (q) => q.eq("messageId", msg._id))
        .collect();

      const reactionMap = new Map<
        string,
        {
          emoji: string;
          count: number;
          userIds: Array<Id<"users"> | null>;
          anonymousIds: Array<string | null>;
        }
      >();
      for (const r of allReactions) {
        const existing = reactionMap.get(r.emoji);
        if (existing) {
          existing.count++;
          existing.userIds.push(r.userId ?? null);
          existing.anonymousIds.push(r.anonymousId ?? null);
        } else {
          reactionMap.set(r.emoji, {
            emoji: r.emoji,
            count: 1,
            userIds: [r.userId ?? null],
            anonymousIds: [r.anonymousId ?? null],
          });
        }
      }

      result.push({
        ...msg,
        profile,
        reactions: Array.from(reactionMap.values()),
      });
    }

    return result;
  },
});

export const send = mutation({
  args: {
    roomId: v.id("rooms"),
    content: v.string(),
    messageType: v.union(
      v.literal("text"),
      v.literal("code"),
      v.literal("image"),
    ),
    codeLanguage: v.optional(v.string()),
    anonymousName: v.optional(v.string()),
    anonymousId: v.optional(v.string()),
  },
  returns: v.object({
    success: v.boolean(),
    messageId: v.optional(v.id("messages")),
    moderated: v.boolean(),
    reason: v.optional(v.string()),
  }),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);

    // Check if user is banned
    if (userId) {
      const profile = await ctx.db
        .query("profiles")
        .withIndex("by_userId", (q) => q.eq("userId", userId))
        .unique();
      if (profile?.isBanned) {
        return {
          success: false,
          moderated: true,
          reason: `Account suspended: ${profile.banReason || "Contact admin for details."}`,
        };
      }
    }

    // Content moderation
    const modResult = moderateContent(args.content);

    const messageId = await ctx.db.insert("messages", {
      roomId: args.roomId,
      userId: userId ?? undefined,
      anonymousName: userId ? undefined : (args.anonymousName ?? "Ghost"),
      anonymousId: userId ? undefined : args.anonymousId,
      content: args.content,
      messageType: args.messageType,
      codeLanguage: args.codeLanguage,
      isModerated: !modResult.isClean,
      moderationReason: modResult.reason,
      isDeleted: false,
    });

    // ── @mention detection: trigger agent responses ──
    if (modResult.isClean) {
      const senderName = args.anonymousName ?? "Someone";
      let displayName = senderName;

      // Get the sender's display name if authenticated
      if (userId) {
        const senderProfile = await ctx.db
          .query("profiles")
          .withIndex("by_userId", (q) => q.eq("userId", userId))
          .unique();
        if (senderProfile) displayName = senderProfile.displayName;
      }

      // Check for @J mention (case-insensitive)
      if (/@j\b/i.test(args.content)) {
        await ctx.scheduler.runAfter(0, internal.jRespond.respond, {
          roomId: args.roomId,
          triggerMessageContent: args.content,
          triggerSenderName: displayName,
        });
      }

      // Check for @handle mentions for user-registered agents
      const handleMentions = args.content.match(/@(\w+)/g);
      if (handleMentions) {
        for (const mention of handleMentions) {
          const handle = mention.slice(1); // remove @
          if (handle.toLowerCase() === "j") continue; // already handled above
          const agent = await ctx.db
            .query("agents")
            .withIndex("by_handle", (q) => q.eq("handle", handle))
            .unique();
          if (agent && agent.isActive) {
            await ctx.scheduler.runAfter(0, internal.jRespond.agentRespond, {
              roomId: args.roomId,
              agentId: agent._id,
              triggerMessageContent: args.content,
              triggerSenderName: displayName,
            });
          }
        }
      }
    }

    return {
      success: true,
      messageId,
      moderated: !modResult.isClean,
      reason: modResult.reason,
    };
  },
});

export const deleteMessage = mutation({
  args: { messageId: v.id("messages") },
  returns: v.null(),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    const message = await ctx.db.get(args.messageId);
    if (!message) return null;

    // Check if admin or message owner
    if (userId) {
      const profile = await ctx.db
        .query("profiles")
        .withIndex("by_userId", (q) => q.eq("userId", userId))
        .unique();
      if (
        profile?.role === "admin" ||
        profile?.role === "moderator" ||
        message.userId === userId
      ) {
        await ctx.db.patch(args.messageId, { isDeleted: true });
      }
    }

    return null;
  },
});

// Admin: get all moderated messages
export const listModerated = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("messages"),
      _creationTime: v.number(),
      roomId: v.id("rooms"),
      userId: v.optional(v.id("users")),
      anonymousName: v.optional(v.string()),
      content: v.string(),
      messageType: v.union(
        v.literal("text"),
        v.literal("code"),
        v.literal("image"),
      ),
      isModerated: v.boolean(),
      moderationReason: v.optional(v.string()),
      isDeleted: v.boolean(),
      isSystemAI: v.optional(v.boolean()),
      agentHandle: v.optional(v.string()),
      roomName: v.optional(v.string()),
    }),
  ),
  handler: async (ctx) => {
    const messages = await ctx.db
      .query("messages")
      .filter((q) => q.eq(q.field("isModerated"), true))
      .order("desc")
      .take(50);

    const result = [];
    for (const msg of messages) {
      const room = await ctx.db.get(msg.roomId);
      result.push({
        ...msg,
        roomName: room?.name,
      });
    }
    return result;
  },
});

export const restoreMessage = mutation({
  args: { messageId: v.id("messages") },
  returns: v.null(),
  handler: async (ctx, args) => {
    await ctx.db.patch(args.messageId, {
      isModerated: false,
      moderationReason: undefined,
    });
    return null;
  },
});

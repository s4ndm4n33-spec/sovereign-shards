import { authTables } from "@convex-dev/auth/server";
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

const schema = defineSchema({
  ...authTables,

  rooms: defineTable({
    name: v.string(),
    description: v.string(),
    icon: v.string(),
    sortOrder: v.number(),
    isDefault: v.boolean(),
  }).index("by_sortOrder", ["sortOrder"]),

  messages: defineTable({
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
  })
    .index("by_room", ["roomId"])
    .index("by_room_moderated", ["roomId", "isModerated"]),

  profiles: defineTable({
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
  })
    .index("by_userId", ["userId"])
    .index("by_handle", ["handle"])
    .index("by_role", ["role"]),

  reactions: defineTable({
    messageId: v.id("messages"),
    userId: v.optional(v.id("users")),
    anonymousId: v.optional(v.string()),
    emoji: v.string(),
  }).index("by_message", ["messageId"]),

  appeals: defineTable({
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
    adminId: v.optional(v.id("users")),
  })
    .index("by_status", ["status"])
    .index("by_message", ["messageId"]),

  adminSessions: defineTable({
    token: v.string(),
    expiresAt: v.number(),
  }).index("by_token", ["token"]),

  agents: defineTable({
    ownerId: v.id("users"),
    name: v.string(),
    handle: v.string(), // invoked via @handle in chat
    description: v.string(),
    endpointUrl: v.string(),
    apiKey: v.optional(v.string()), // stored server-side, never sent to client
    authHeader: v.optional(v.string()), // e.g. "Authorization" or "X-API-Key"
    model: v.optional(v.string()), // model name if applicable
    isPublic: v.boolean(),
    isActive: v.boolean(),
    totalInvocations: v.number(),
  })
    .index("by_owner", ["ownerId"])
    .index("by_handle", ["handle"])
    .index("by_isPublic", ["isPublic"]),

  onlinePresence: defineTable({
    userId: v.optional(v.id("users")),
    anonymousId: v.optional(v.string()),
    displayName: v.string(),
    roomId: v.id("rooms"),
    lastSeen: v.number(),
  })
    .index("by_room", ["roomId"])
    .index("by_userId", ["userId"]),
});

export default schema;

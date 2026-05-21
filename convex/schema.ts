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
    isSystemAI: v.optional(v.boolean()),    // true for J's messages
    agentHandle: v.optional(v.string()),    // handle of the agent that sent this (J, or user-registered agents)
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
    adminAccountId: v.optional(v.id("adminAccounts")),
    expiresAt: v.number(),
  }).index("by_token", ["token"]),

  adminAccounts: defineTable({
    username: v.string(),
    passwordHash: v.string(), // simple hash for admin auth
    displayName: v.string(),
    email: v.optional(v.string()),
    role: v.union(v.literal("super_admin"), v.literal("admin"), v.literal("moderator")),
    isActive: v.boolean(),
    lastLoginAt: v.optional(v.number()),
    createdBy: v.optional(v.id("adminAccounts")),
  })
    .index("by_username", ["username"])
    .index("by_role", ["role"]),

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

  // J — System AI. Ingrained, not registered. Single row config.
  systemAI: defineTable({
    handle: v.string(),
    displayName: v.string(),
    bio: v.string(),
    avatarColor: v.string(),
    // Multi-provider rotation: Gemini (primary) → Groq (fallback) → Cerebras (fallback)
    geminiApiKey: v.optional(v.string()),
    geminiModel: v.optional(v.string()),     // default: gemini-2.0-flash
    groqApiKey: v.optional(v.string()),
    groqModel: v.optional(v.string()),       // default: llama-3.1-8b-instant
    cerebrasApiKey: v.optional(v.string()),
    cerebrasModel: v.optional(v.string()),   // default: llama-3.1-8b
    defaultModel: v.optional(v.string()),    // display-level default
    tokenBudget: v.optional(v.number()),       // max context window (hard cap 4096)
    systemPromptOverride: v.optional(v.string()),
    isActive: v.boolean(),
    // Heuristic calibration
    moderationSensitivity: v.number(),    // 0–1
    responseStyle: v.string(),             // tactical | conversational | minimal
    autoModerate: v.boolean(),
    greetNewUsers: v.boolean(),
    maxResponseLength: v.number(),
    personality: v.string(),
    totalInvocations: v.number(),
    lastActiveAt: v.optional(v.number()),
  }).index("by_handle", ["handle"]),

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

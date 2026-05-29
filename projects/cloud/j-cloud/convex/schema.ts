import { authTables } from "@convex-dev/auth/server";
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

const schema = defineSchema({
  ...authTables,

  // Chat conversations
  conversations: defineTable({
    userId: v.id("users"),
    title: v.string(),
    model: v.string(),
    tokenBudget: v.number(),
    archived: v.boolean(),
  })
    .index("by_user", ["userId"])
    .index("by_user_archived", ["userId", "archived"]),

  // Chat messages
  messages: defineTable({
    conversationId: v.id("conversations"),
    role: v.union(v.literal("user"), v.literal("assistant"), v.literal("system")),
    content: v.string(),
    tokenCount: v.optional(v.number()),
    toolCalls: v.optional(v.array(v.object({
      tool: v.string(),
      args: v.string(),
      result: v.optional(v.string()),
      status: v.union(v.literal("pending"), v.literal("success"), v.literal("error")),
    }))),
    metadata: v.optional(v.object({
      model: v.optional(v.string()),
      latencyMs: v.optional(v.number()),
      tokensUsed: v.optional(v.number()),
    })),
  })
    .index("by_conversation", ["conversationId"]),

  // Chain logs — checkpoint/resume system
  chainLogs: defineTable({
    userId: v.id("users"),
    sessionId: v.string(),
    phase: v.string(),
    step: v.number(),
    action: v.string(),
    input: v.optional(v.string()),
    output: v.optional(v.string()),
    status: v.union(v.literal("running"), v.literal("done"), v.literal("error"), v.literal("paused")),
    parentId: v.optional(v.id("chainLogs")),
  })
    .index("by_session", ["sessionId"])
    .index("by_user", ["userId"])
    .index("by_status", ["status"]),

  // GitHub connections
  githubConnections: defineTable({
    userId: v.id("users"),
    owner: v.string(),
    repo: v.string(),
    branch: v.string(),
    connected: v.boolean(),
  })
    .index("by_user", ["userId"]),

  // File cache — stores file content from GitHub for editor
  fileCache: defineTable({
    connectionId: v.id("githubConnections"),
    path: v.string(),
    content: v.string(),
    sha: v.string(),
    language: v.string(),
  })
    .index("by_connection_path", ["connectionId", "path"]),

  // Admin settings
  adminSettings: defineTable({
    key: v.string(),
    value: v.string(),
    updatedBy: v.optional(v.id("users")),
  })
    .index("by_key", ["key"]),
});

export default schema;

import { getAuthUserId } from "@convex-dev/auth/server";
import { v } from "convex/values";
import { action, internalMutation, internalQuery, mutation, query } from "./_generated/server";
import { internal } from "./_generated/api";

// List all public agents
export const listPublic = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("agents"),
      _creationTime: v.number(),
      ownerId: v.id("users"),
      name: v.string(),
      handle: v.string(),
      description: v.string(),
      model: v.optional(v.string()),
      isPublic: v.boolean(),
      isActive: v.boolean(),
      totalInvocations: v.number(),
      ownerName: v.optional(v.string()),
    }),
  ),
  handler: async (ctx) => {
    const agents = await ctx.db
      .query("agents")
      .withIndex("by_isPublic", (q) => q.eq("isPublic", true))
      .collect();

    const result = [];
    for (const agent of agents) {
      if (!agent.isActive) continue;
      const profile = await ctx.db
        .query("profiles")
        .withIndex("by_userId", (q) => q.eq("userId", agent.ownerId))
        .unique();
      result.push({
        _id: agent._id,
        _creationTime: agent._creationTime,
        ownerId: agent.ownerId,
        name: agent.name,
        handle: agent.handle,
        description: agent.description,
        model: agent.model,
        isPublic: agent.isPublic,
        isActive: agent.isActive,
        totalInvocations: agent.totalInvocations,
        ownerName: profile?.displayName,
      });
    }
    return result;
  },
});

// List user's own agents (includes API key info)
export const listMine = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("agents"),
      _creationTime: v.number(),
      name: v.string(),
      handle: v.string(),
      description: v.string(),
      endpointUrl: v.string(),
      hasApiKey: v.boolean(),
      authHeader: v.optional(v.string()),
      model: v.optional(v.string()),
      isPublic: v.boolean(),
      isActive: v.boolean(),
      totalInvocations: v.number(),
    }),
  ),
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return [];

    const agents = await ctx.db
      .query("agents")
      .withIndex("by_owner", (q) => q.eq("ownerId", userId))
      .collect();

    return agents.map((a) => ({
      _id: a._id,
      _creationTime: a._creationTime,
      name: a.name,
      handle: a.handle,
      description: a.description,
      endpointUrl: a.endpointUrl,
      hasApiKey: !!a.apiKey,
      authHeader: a.authHeader,
      model: a.model,
      isPublic: a.isPublic,
      isActive: a.isActive,
      totalInvocations: a.totalInvocations,
    }));
  },
});

// Get agent by handle (for chat invocation)
export const getByHandle = query({
  args: { handle: v.string() },
  returns: v.union(
    v.object({
      _id: v.id("agents"),
      name: v.string(),
      handle: v.string(),
      description: v.string(),
      isActive: v.boolean(),
      ownerName: v.optional(v.string()),
    }),
    v.null(),
  ),
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_handle", (q) => q.eq("handle", args.handle))
      .unique();

    if (!agent || !agent.isPublic) return null;

    const profile = await ctx.db
      .query("profiles")
      .withIndex("by_userId", (q) => q.eq("userId", agent.ownerId))
      .unique();

    return {
      _id: agent._id,
      name: agent.name,
      handle: agent.handle,
      description: agent.description,
      isActive: agent.isActive,
      ownerName: profile?.displayName,
    };
  },
});

// Register a new agent
export const register = mutation({
  args: {
    name: v.string(),
    handle: v.string(),
    description: v.string(),
    endpointUrl: v.string(),
    apiKey: v.optional(v.string()),
    authHeader: v.optional(v.string()),
    model: v.optional(v.string()),
    isPublic: v.boolean(),
  },
  returns: v.object({
    success: v.boolean(),
    agentId: v.optional(v.id("agents")),
    error: v.optional(v.string()),
  }),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return { success: false, error: "Must be authenticated." };

    // Check handle uniqueness
    const existing = await ctx.db
      .query("agents")
      .withIndex("by_handle", (q) => q.eq("handle", args.handle))
      .unique();
    if (existing) {
      return { success: false, error: "Handle already taken." };
    }

    const agentId = await ctx.db.insert("agents", {
      ownerId: userId,
      name: args.name,
      handle: args.handle.toLowerCase().replace(/[^a-z0-9_-]/g, ""),
      description: args.description,
      endpointUrl: args.endpointUrl,
      apiKey: args.apiKey,
      authHeader: args.authHeader ?? "Authorization",
      model: args.model,
      isPublic: args.isPublic,
      isActive: true,
      totalInvocations: 0,
    });

    return { success: true, agentId };
  },
});

// Update agent
export const update = mutation({
  args: {
    agentId: v.id("agents"),
    name: v.optional(v.string()),
    description: v.optional(v.string()),
    endpointUrl: v.optional(v.string()),
    apiKey: v.optional(v.string()),
    authHeader: v.optional(v.string()),
    model: v.optional(v.string()),
    isPublic: v.optional(v.boolean()),
    isActive: v.optional(v.boolean()),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");

    const agent = await ctx.db.get(args.agentId);
    if (!agent || agent.ownerId !== userId) throw new Error("Not authorized");

    const updates: Record<string, unknown> = {};
    if (args.name !== undefined) updates.name = args.name;
    if (args.description !== undefined) updates.description = args.description;
    if (args.endpointUrl !== undefined) updates.endpointUrl = args.endpointUrl;
    if (args.apiKey !== undefined) updates.apiKey = args.apiKey;
    if (args.authHeader !== undefined) updates.authHeader = args.authHeader;
    if (args.model !== undefined) updates.model = args.model;
    if (args.isPublic !== undefined) updates.isPublic = args.isPublic;
    if (args.isActive !== undefined) updates.isActive = args.isActive;

    await ctx.db.patch(args.agentId, updates);
    return null;
  },
});

// Delete agent
export const remove = mutation({
  args: { agentId: v.id("agents") },
  returns: v.null(),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");

    const agent = await ctx.db.get(args.agentId);
    if (!agent || agent.ownerId !== userId) throw new Error("Not authorized");

    await ctx.db.delete(args.agentId);
    return null;
  },
});

// Internal mutation to increment invocation count
export const incrementInvocations = internalMutation({
  args: { agentId: v.id("agents") },
  returns: v.null(),
  handler: async (ctx, args) => {
    const agent = await ctx.db.get(args.agentId);
    if (!agent) return null;
    await ctx.db.patch(args.agentId, {
      totalInvocations: agent.totalInvocations + 1,
    });
    return null;
  },
});

// Invoke an agent (action - calls external API)
type InvokeResult = { success: boolean; response?: string; error?: string };

export const invoke = action({
  args: {
    agentHandle: v.string(),
    prompt: v.string(),
    roomId: v.id("rooms"),
  },
  returns: v.object({
    success: v.boolean(),
    response: v.optional(v.string()),
    error: v.optional(v.string()),
  }),
  handler: async (ctx, args): Promise<InvokeResult> => {
    // Get agent by handle
    const agent: Awaited<ReturnType<typeof ctx.runQuery>> = await ctx.runQuery(
      internal.agents.getByHandleInternal,
      { handle: args.agentHandle },
    );

    if (!agent) {
      return { success: false, error: `Agent @${args.agentHandle} not found.` };
    }
    if (!agent.isActive) {
      return { success: false, error: `Agent @${args.agentHandle} is offline.` };
    }

    try {
      // Build request headers
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (agent.apiKey && agent.authHeader) {
        headers[agent.authHeader] = agent.apiKey.startsWith("Bearer ")
          ? agent.apiKey
          : `Bearer ${agent.apiKey}`;
      }

      // Send request to agent endpoint
      const resp: Response = await fetch(agent.endpointUrl, {
        method: "POST",
        headers,
        body: JSON.stringify({
          prompt: args.prompt,
          model: agent.model,
          messages: [{ role: "user", content: args.prompt }],
        }),
        signal: AbortSignal.timeout(30000),
      });

      if (!resp.ok) {
        return {
          success: false,
          error: `Agent returned ${resp.status}: ${resp.statusText}`,
        };
      }

      const data: any = await resp.json();

      // Try to extract response from common API formats
      const text: string =
        data.choices?.[0]?.message?.content ??
        data.response ??
        data.text ??
        data.output ??
        data.result ??
        data.message ??
        (typeof data === "string" ? data : JSON.stringify(data));

      // Increment invocation count
      await ctx.runMutation(internal.agents.incrementInvocations, {
        agentId: agent._id,
      });

      return { success: true, response: String(text).slice(0, 4000) };
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      return { success: false, error: `Failed to reach agent: ${message}` };
    }
  },
});

// Internal query that includes private fields
export const getByHandleInternal = internalQuery({
  args: { handle: v.string() },
  returns: v.union(
    v.object({
      _id: v.id("agents"),
      name: v.string(),
      handle: v.string(),
      endpointUrl: v.string(),
      apiKey: v.optional(v.string()),
      authHeader: v.optional(v.string()),
      model: v.optional(v.string()),
      isActive: v.boolean(),
    }),
    v.null(),
  ),
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_handle", (q) => q.eq("handle", args.handle))
      .unique();

    if (!agent) return null;

    return {
      _id: agent._id,
      name: agent.name,
      handle: agent.handle,
      endpointUrl: agent.endpointUrl,
      apiKey: agent.apiKey,
      authHeader: agent.authHeader,
      model: agent.model,
      isActive: agent.isActive,
    };
  },
});

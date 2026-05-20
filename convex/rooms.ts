import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const list = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("rooms"),
      _creationTime: v.number(),
      name: v.string(),
      description: v.string(),
      icon: v.string(),
      sortOrder: v.number(),
      isDefault: v.boolean(),
    }),
  ),
  handler: async (ctx) => {
    return await ctx.db.query("rooms").withIndex("by_sortOrder").collect();
  },
});

export const get = query({
  args: { roomId: v.id("rooms") },
  returns: v.union(
    v.object({
      _id: v.id("rooms"),
      _creationTime: v.number(),
      name: v.string(),
      description: v.string(),
      icon: v.string(),
      sortOrder: v.number(),
      isDefault: v.boolean(),
    }),
    v.null(),
  ),
  handler: async (ctx, args) => {
    return await ctx.db.get(args.roomId);
  },
});

export const seed = mutation({
  args: {},
  returns: v.null(),
  handler: async (ctx) => {
    const existing = await ctx.db.query("rooms").first();
    if (existing) return null;

    const rooms = [
      {
        name: "general",
        description: "Main comms channel. All operators welcome.",
        icon: "⬡",
        sortOrder: 0,
        isDefault: true,
      },
      {
        name: "runtime",
        description: "Runtime architecture, execution engines, orchestration.",
        icon: "◈",
        sortOrder: 1,
        isDefault: false,
      },
      {
        name: "memory",
        description: "Persistence layers, memory reconstruction, state management.",
        icon: "◇",
        sortOrder: 2,
        isDefault: false,
      },
      {
        name: "integrity",
        description: "Validation, verification, security hardening.",
        icon: "△",
        sortOrder: 3,
        isDefault: false,
      },
      {
        name: "showcase",
        description: "Share your builds, demos, and shard deployments.",
        icon: "◎",
        sortOrder: 4,
        isDefault: false,
      },
    ];

    for (const room of rooms) {
      await ctx.db.insert("rooms", room);
    }

    // Seed B.L.U.E.-J. as the system AI agent profile (anonymous/system presence)
    const existingAgent = await ctx.db
      .query("agents")
      .withIndex("by_handle", (q) => q.eq("handle", "bluej"))
      .unique();

    if (!existingAgent) {
      // J is pre-registered but has no owner yet — Mike will claim and set API keys from his profile.
      // For now, create a placeholder profile entry for J's chat presence.
      // The agent record needs an ownerId, so we skip it here —
      // it'll be created when Mike registers from his profile.
    }

    return null;
  },
});

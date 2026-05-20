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

// Admin-only: create a new room
export const createRoom = mutation({
  args: {
    name: v.string(),
    description: v.string(),
    icon: v.string(),
  },
  handler: async (ctx, args) => {
    // Get max sortOrder
    const allRooms = await ctx.db.query("rooms").withIndex("by_sortOrder").collect();
    const maxSort = allRooms.length > 0 ? Math.max(...allRooms.map((r) => r.sortOrder)) : -1;

    const id = await ctx.db.insert("rooms", {
      name: args.name.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""),
      description: args.description,
      icon: args.icon || "◆",
      sortOrder: maxSort + 1,
      isDefault: false,
    });
    return { roomId: id };
  },
});

// Admin-only: update a room
export const updateRoom = mutation({
  args: {
    roomId: v.id("rooms"),
    name: v.optional(v.string()),
    description: v.optional(v.string()),
    icon: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const room = await ctx.db.get(args.roomId);
    if (!room) return { success: false };

    const updates: Record<string, any> = {};
    if (args.name !== undefined) updates.name = args.name.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
    if (args.description !== undefined) updates.description = args.description;
    if (args.icon !== undefined) updates.icon = args.icon;

    await ctx.db.patch(args.roomId, updates);
    return { success: true };
  },
});

// Admin-only: delete a room (non-default only)
export const deleteRoom = mutation({
  args: { roomId: v.id("rooms") },
  handler: async (ctx, args) => {
    const room = await ctx.db.get(args.roomId);
    if (!room || room.isDefault) return { success: false };
    await ctx.db.delete(args.roomId);
    return { success: true };
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

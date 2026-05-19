import { v } from "convex/values";
import { action, mutation, query } from "./_generated/server";

declare const process: { env: Record<string, string | undefined> };

const VIKTOR_API_URL = process.env.VIKTOR_SPACES_API_URL!;
const PROJECT_NAME = process.env.VIKTOR_SPACES_PROJECT_NAME!;
const PROJECT_SECRET = process.env.VIKTOR_SPACES_PROJECT_SECRET!;

async function callTool<T>(role: string, args: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(`${VIKTOR_API_URL}/api/viktor-spaces/tools/call`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_name: PROJECT_NAME,
      project_secret: PROJECT_SECRET,
      role,
      arguments: args,
    }),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  const json = await response.json();
  if (!json.success) {
    throw new Error(json.error ?? "Tool call failed");
  }
  return json.result as T;
}

// Create a pre-order
export const create = mutation({
  args: {
    name: v.string(),
    email: v.string(),
    tier: v.string(),
    amount: v.number(),
    notes: v.optional(v.string()),
  },
  returns: v.id("preorders"),
  handler: async (ctx, { name, email, tier, amount, notes }) => {
    return await ctx.db.insert("preorders", {
      name,
      email,
      tier,
      amount,
      status: "pending",
      notes,
      createdAt: Date.now(),
    });
  },
});

// Send notification email after pre-order
export const sendNotification = action({
  args: {
    name: v.string(),
    email: v.string(),
    tier: v.string(),
    amount: v.number(),
  },
  returns: v.boolean(),
  handler: async (_ctx, { name, email, tier, amount }) => {
    try {
      await callTool<{ success: boolean }>("coworker_send_email", {
        to: "vikvondoom2026@gmail.com",
        subject: `🔥 New Sovereign Shards Pre-Order: ${tier} — ${name}`,
        body: `New pre-order received!\n\nName: ${name}\nEmail: ${email}\nTier: ${tier}\nAmount: $${(amount / 100).toFixed(2)}\nTime: ${new Date().toISOString()}\n\n---\nSovereign Shards Pre-Order System`,
      });
      return true;
    } catch (e) {
      console.error("Failed to send notification:", e);
      return false;
    }
  },
});

// List all pre-orders (admin)
export const list = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("preorders"),
      _creationTime: v.number(),
      name: v.string(),
      email: v.string(),
      tier: v.string(),
      amount: v.number(),
      status: v.string(),
      notes: v.optional(v.string()),
      createdAt: v.number(),
    })
  ),
  handler: async (ctx) => {
    return await ctx.db.query("preorders").order("desc").collect();
  },
});

// Count pre-orders
export const count = query({
  args: {},
  returns: v.number(),
  handler: async (ctx) => {
    const all = await ctx.db.query("preorders").collect();
    return all.length;
  },
});

// Update pre-order status (admin)
export const updateStatus = mutation({
  args: {
    id: v.id("preorders"),
    status: v.string(),
  },
  returns: v.null(),
  handler: async (ctx, { id, status }) => {
    await ctx.db.patch(id, { status });
    return null;
  },
});

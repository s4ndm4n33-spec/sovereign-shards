import { getAuthUserId } from "@convex-dev/auth/server";
import { action, mutation, query, internalQuery } from "./_generated/server";
import { internal } from "./_generated/api";
import { v } from "convex/values";

// --- Queries ---

export const getConnection = query({
  args: {},
  returns: v.union(
    v.object({
      _id: v.id("githubConnections"),
      owner: v.string(),
      repo: v.string(),
      branch: v.string(),
      connected: v.boolean(),
    }),
    v.null()
  ),
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) return null;
    const conn = await ctx.db
      .query("githubConnections")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .first();
    if (!conn) return null;
    return {
      _id: conn._id,
      owner: conn.owner,
      repo: conn.repo,
      branch: conn.branch,
      connected: conn.connected,
    };
  },
});

export const getConnectionInternal = internalQuery({
  args: { userId: v.id("users") },
  returns: v.union(
    v.object({
      _id: v.id("githubConnections"),
      owner: v.string(),
      repo: v.string(),
      branch: v.string(),
      connected: v.boolean(),
    }),
    v.null()
  ),
  handler: async (ctx, args) => {
    const conn = await ctx.db
      .query("githubConnections")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .first();
    if (!conn) return null;
    return {
      _id: conn._id,
      owner: conn.owner,
      repo: conn.repo,
      branch: conn.branch,
      connected: conn.connected,
    };
  },
});

// --- Mutations ---

export const connect = mutation({
  args: {
    owner: v.string(),
    repo: v.string(),
    branch: v.optional(v.string()),
  },
  returns: v.id("githubConnections"),
  handler: async (ctx, args) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");

    // Remove existing connections
    const existing = await ctx.db
      .query("githubConnections")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .collect();
    for (const conn of existing) {
      // Clean file cache
      const files = await ctx.db
        .query("fileCache")
        .withIndex("by_connection_path", (q) => q.eq("connectionId", conn._id))
        .collect();
      for (const f of files) await ctx.db.delete(f._id);
      await ctx.db.delete(conn._id);
    }

    return await ctx.db.insert("githubConnections", {
      userId,
      owner: args.owner,
      repo: args.repo,
      branch: args.branch || "main",
      connected: true,
    });
  },
});

export const disconnect = mutation({
  args: {},
  returns: v.null(),
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    const conns = await ctx.db
      .query("githubConnections")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .collect();
    for (const conn of conns) {
      const files = await ctx.db
        .query("fileCache")
        .withIndex("by_connection_path", (q) => q.eq("connectionId", conn._id))
        .collect();
      for (const f of files) await ctx.db.delete(f._id);
      await ctx.db.delete(conn._id);
    }
    return null;
  },
});

// --- Actions (GitHub API calls) ---
// Uses github_token from admin settings for authenticated requests (higher rate limits + private repos).

async function getGithubHeaders(ctx: any): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    Accept: "application/vnd.github.v3+json",
    "User-Agent": "J-Cloud-Agent/1.0",
  };

  // 1. Check env var first
  const envToken = process.env.GITHUB_TOKEN;
  if (envToken && envToken.length > 0) {
    headers["Authorization"] = `Bearer ${envToken}`;
    return headers;
  }

  // 2. Fallback: admin settings
  try {
    const token = await ctx.runQuery(internal.admin.getSettingInternal, {
      key: "github_token",
    });
    if (token && token.length > 0) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  } catch {
    // No token — unauthenticated (60 req/hr for public repos only)
  }
  return headers;
}

export const fetchRepoTree = action({
  args: {
    owner: v.string(),
    repo: v.string(),
    branch: v.optional(v.string()),
    path: v.optional(v.string()),
  },
  returns: v.array(v.object({
    name: v.string(),
    path: v.string(),
    type: v.union(v.literal("file"), v.literal("dir")),
    size: v.optional(v.number()),
  })),
  handler: async (ctx, args) => {
    const branch = args.branch || "main";
    const dirPath = args.path || "";
    const url = `https://api.github.com/repos/${args.owner}/${args.repo}/contents/${dirPath}?ref=${branch}`;
    const headers = await getGithubHeaders(ctx);

    const response = await fetch(url, { headers });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`GitHub API error ${response.status}: ${errText}`);
    }

    const data = await response.json();
    if (!Array.isArray(data)) {
      return [{ name: data.name, path: data.path, type: "file" as const, size: data.size }];
    }

    return data.map((item: { name: string; path: string; type: string; size?: number }) => ({
      name: item.name,
      path: item.path,
      type: (item.type === "dir" ? "dir" : "file") as "file" | "dir",
      size: item.size,
    }));
  },
});

export const fetchFileContent = action({
  args: {
    owner: v.string(),
    repo: v.string(),
    path: v.string(),
    branch: v.optional(v.string()),
  },
  returns: v.object({
    content: v.string(),
    sha: v.string(),
    size: v.number(),
  }),
  handler: async (ctx, args) => {
    const branch = args.branch || "main";
    const url = `https://api.github.com/repos/${args.owner}/${args.repo}/contents/${args.path}?ref=${branch}`;
    const headers = await getGithubHeaders(ctx);

    const response = await fetch(url, { headers });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`GitHub API error ${response.status}: ${errText}`);
    }

    const data = await response.json();
    const content = atob(data.content.replace(/\n/g, ""));

    return {
      content,
      sha: data.sha,
      size: data.size,
    };
  },
});

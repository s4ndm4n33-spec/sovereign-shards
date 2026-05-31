// Copyright (c) 2026 Mike McCollum
//
// Licensed under the Sovereign Shards License.
// See LICENSE.md for details.

import { authTables } from "@convex-dev/auth/server";
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

const schema = defineSchema({
  ...authTables,
  preorders: defineTable({
    name: v.string(),
    email: v.string(),
    tier: v.string(), // "standard" | "dev" | "enterprise"
    amount: v.number(), // price in cents
    status: v.string(), // "pending" | "confirmed" | "cancelled"
    notes: v.optional(v.string()),
    createdAt: v.number(),
  })
    .index("by_email", ["email"])
    .index("by_status", ["status"])
    .index("by_createdAt", ["createdAt"]),
});

export default schema;

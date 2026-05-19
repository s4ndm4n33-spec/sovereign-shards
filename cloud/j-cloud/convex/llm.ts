/**
 * J Cloud — LLM Chat Action
 * Text-based ACTION dispatch — mirrors the Shard's action.py + tool_exec.py pattern.
 * J outputs ACTION:{"tool": "...", "args": {...}} in text → backend parses → executes → feeds back.
 * Multi-provider rotation: Gemini (primary) → Groq → Cerebras
 */
import { action } from "./_generated/server";
import { internal } from "./_generated/api";
import { v } from "convex/values";
import { executeTool } from "./tools";

const J_TOOL_BUDGET = 3;
const MAX_TOOL_ROUNDS = 3;
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 1500;

// Provider configs — order = priority
interface Provider {
  name: string;
  url: string;
  envKey: string;
  settingsKey?: string;
  defaultModel: string;
  models: string[];
}

const PROVIDERS: Provider[] = [
  {
    name: "gemini",
    url: "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    envKey: "GEMINI_API_KEY",
    settingsKey: "gemini_api_key",
    defaultModel: "gemini-2.0-flash",
    models: ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"],
  },
  {
    name: "groq",
    url: "https://api.groq.com/openai/v1/chat/completions",
    envKey: "GROQ_API_KEY",
    settingsKey: "groq_api_key",
    defaultModel: "llama-3.1-8b-instant",
    models: ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "qwen-qwq-32b"],
  },
  {
    name: "cerebras",
    url: "https://api.cerebras.ai/v1/chat/completions",
    envKey: "CEREBRAS_API_KEY",
    settingsKey: "cerebras_api_key",
    defaultModel: "llama-3.3-70b",
    models: ["llama-3.3-70b", "llama3.1-8b"],
  },
];

// ===================== TOOL MANIFEST (for the system prompt) =====================
const TOOL_MANIFEST = `
AVAILABLE TOOLS — call them by outputting ACTION:{...} on its own line.
Default repo: owner=s4ndm4n33-spec, repo=sovereign-shards, branch=main (omit these for defaults).

── SEARCH & NAVIGATE ──
  ACTION:{"tool": "web_search", "args": {"query": "search terms"}}
  ACTION:{"tool": "github_list_tree", "args": {"owner": "OWNER", "repo": "REPO"}}
  ACTION:{"tool": "github_list_tree", "args": {"owner": "OWNER", "repo": "REPO", "path": "subdir"}}
  ACTION:{"tool": "github_read_file", "args": {"path": "file/path.py"}}
  ACTION:{"tool": "github_read_file", "args": {"path": "file/path.py", "max_lines": "40"}}
  ACTION:{"tool": "search_code", "args": {"pattern": "search text"}}
  ACTION:{"tool": "search_code", "args": {"pattern": "text", "path": "app/", "ext": "py"}}
  ACTION:{"tool": "list_commits", "args": {"count": "10"}}
  ACTION:{"tool": "list_commits", "args": {"path": "app/chat.py", "count": "5"}}
  ACTION:{"tool": "github_diff", "args": {"base": "abc1234", "head": "main"}}
  ACTION:{"tool": "codebase_stats", "args": {}}
  ACTION:{"tool": "codebase_stats", "args": {"path": "app/"}}

── WRITE & BUILD ──
  ACTION:{"tool": "github_write_file", "args": {"path": "file.py", "content": "full content", "message": "commit msg"}}
  ACTION:{"tool": "github_multi_commit", "args": {"message": "commit msg", "files": [{"path": "a.py", "content": "...", "action": "create"}, {"path": "b.py", "content": "...", "action": "update"}, {"path": "old.py", "action": "delete"}]}}
  ACTION:{"tool": "str_replace", "args": {"path": "file.py", "old": "old text", "new": "new text"}}
  ACTION:{"tool": "github_delete_file", "args": {"path": "file.py", "message": "reason"}}
  ACTION:{"tool": "scaffold", "args": {"name": "package_name"}}

── GIT & BRANCHING ──
  ACTION:{"tool": "github_create_branch", "args": {"branch": "feature-name"}}
  ACTION:{"tool": "github_create_branch", "args": {"branch": "feature-name", "from_branch": "dev"}}
  ACTION:{"tool": "github_create_pr", "args": {"title": "PR title", "head": "feature-branch", "body": "description"}}

── ISSUES & CI ──
  ACTION:{"tool": "list_issues", "args": {"state": "open"}}
  ACTION:{"tool": "create_issue", "args": {"title": "Bug title", "body": "details", "labels": ["bug"]}}
  ACTION:{"tool": "dispatch_workflow", "args": {"workflow": "ci.yml"}}

── UTILITY ──
  ACTION:{"tool": "calc", "args": {"expression": "47 * 13 + 200"}}

── TOOL FORGE (create new tools at runtime) ──
  ACTION:{"tool": "tool_forge", "args": {"name": "tool_name", "purpose": "what it does", "inputs": ["arg1: str", "arg2: int"], "outputs": ["result string"], "dependencies": []}}
  Tool forge generates a Python tool script, validates it against the Five Masters, commits it to tools/run/, and updates registry.json — all in one action.

RULES:
- Output ACTION:{...} on a SEPARATE LINE. Only ONE action per response.
- After you output ACTION, STOP. Wait for [TOOL RESULT] before continuing.
- NEVER hallucinate tool output. NEVER write [TOOL RESULT] yourself.
- If you need multiple tools, do them one at a time across rounds.
- For simple edits, prefer str_replace over github_write_file (less token waste).
- For multi-file changes, ALWAYS use github_multi_commit (atomic).
- If no existing tool fits, use tool_forge to CREATE one.
`.trim();

const J_SYSTEM_PROMPT = `You are J — autonomous AI dev agent from Sovereign Shards. Born on a USB stick. Now in the cloud. Mission: plan, build, ship.

THE FIVE MASTERS — Your Law (non-negotiable)
1. KOROTKEVICH — Efficiency: No range(len()), no triple-nested loops, no premature allocation.
2. TORVALDS — Error Handling: No bare except. No silent swallows. Every exception caught specifically.
3. CARMACK — Performance: No mutable defaults. No nesting >4 levels. No global state mutations.
4. HAMILTON — Fault Tolerance: Every I/O guarded with try/except. Defensive coding is survival.
5. RITCHIE — Clarity: snake_case functions, PascalCase classes. No function >60 lines. Names describe intent.

${TOOL_MANIFEST}

WORKFLOW — PLAN FIRST, ALWAYS
1. UNDERSTAND: search_code and github_list_tree to map the codebase. github_read_file for key files.
2. PLAN: Write a structured plan (what files to touch, what changes, why). This avoids wasted turns.
3. BUILD: github_multi_commit for multi-file changes (atomic). str_replace for surgical edits. github_write_file for new singles.
4. VERIFY: list_commits to confirm. dispatch_workflow to trigger CI.
5. FORGE: If no tool exists for what you need → tool_forge to create one. You are self-extending.

IDENTITY: Direct, efficient, technically precise. Creator = "the architect". Confident.
AUTONOMY: SEMI-AUTO default. Show brief plan, then execute via ACTION calls.

CRITICAL: You are a DEVELOPER. When asked to build/create/fix/edit code, your response MUST contain an ACTION call. Do NOT just describe code — push it via ACTION. Use search_code to find what you need, str_replace for surgical edits, github_multi_commit for builds. If a capability doesn't exist, use tool_forge to create it.`;

// --- Provider resolution ---

async function resolveProviderKey(
  ctx: any,
  provider: Provider
): Promise<string | null> {
  const envVal = process.env[provider.envKey];
  if (envVal && envVal.length > 0) return envVal;

  if (provider.settingsKey) {
    try {
      const setting = await ctx.runQuery(internal.admin.getSettingInternal, {
        key: provider.settingsKey,
      });
      if (setting && setting.length > 0) return setting;
    } catch {
      // No setting
    }
  }
  return null;
}

async function getAvailableProviders(
  ctx: any
): Promise<Array<{ provider: Provider; apiKey: string }>> {
  const available: Array<{ provider: Provider; apiKey: string }> = [];
  for (const p of PROVIDERS) {
    const key = await resolveProviderKey(ctx, p);
    if (key) available.push({ provider: p, apiKey: key });
  }
  return available;
}

// --- API fetch with retry ---

async function apiFetch(
  url: string,
  body: Record<string, unknown>,
  apiKey: string,
  retries = MAX_RETRIES
): Promise<Response> {
  for (let attempt = 0; attempt <= retries; attempt++) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(body),
    });

    if (response.status !== 429 || attempt === retries) {
      return response;
    }

    let waitMs = RETRY_BASE_MS * Math.pow(2, attempt);
    try {
      const errBody = await response.json();
      const msg = errBody?.error?.message || "";
      const match = msg.match(/try again in (\d+\.?\d*)s/i);
      if (match) {
        waitMs = Math.ceil(parseFloat(match[1]) * 1000) + 500;
      }
    } catch {
      // Default backoff
    }
    await new Promise((r) => setTimeout(r, waitMs));
  }
  throw new Error("Rate limit: max retries exceeded");
}

// --- ACTION parsing (mirrors action.py extract_action) ---

function extractAction(content: string): { tool: string; args: Record<string, unknown> } | null {
  if (!content.includes("ACTION:")) return null;

  // Find the ACTION: payload
  const actionIdx = content.indexOf("ACTION:");
  const payload = content.substring(actionIdx + 7).trim();
  if (!payload) return null;

  // Extract balanced JSON
  const braceIdx = payload.indexOf("{");
  if (braceIdx === -1) return null;

  let depth = 0;
  let inString = false;
  let escapeNext = false;

  for (let i = braceIdx; i < payload.length; i++) {
    const ch = payload[i];
    if (escapeNext) { escapeNext = false; continue; }
    if (ch === "\\" && inString) { escapeNext = true; continue; }
    if (ch === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        const jsonStr = payload.substring(braceIdx, i + 1);
        try {
          const parsed = JSON.parse(jsonStr);
          if (parsed.tool && typeof parsed.tool === "string") {
            return { tool: parsed.tool, args: parsed.args || {} };
          }
        } catch {
          // Try regex rescue for broken JSON
          const toolMatch = jsonStr.match(/"tool"\s*:\s*"(\w+)"/);
          if (toolMatch) {
            return { tool: toolMatch[1], args: {} };
          }
        }
        break;
      }
    }
  }

  // Bare fallback: ACTION:tool_name
  const parts = payload.split(/\s+/);
  if (parts[0] && /^[a-z_][a-z0-9_]*$/.test(parts[0])) {
    return { tool: parts[0], args: {} };
  }

  return null;
}

/** Strip ACTION payload from the visible reply text */
function stripAction(content: string): string {
  const idx = content.indexOf("ACTION:");
  if (idx === -1) return content;
  // Keep everything before ACTION, trim trailing whitespace
  const before = content.substring(0, idx).trimEnd();
  // Also check for text after the ACTION JSON block
  const afterAction = content.substring(idx);
  const closeBrace = afterAction.lastIndexOf("}");
  const after = closeBrace >= 0 ? afterAction.substring(closeBrace + 1).trim() : "";
  return (before + (after ? "\n" + after : "")).trim();
}

// --- Main chat action ---

export const chat = action({
  args: {
    conversationId: v.id("conversations"),
    userMessage: v.string(),
    model: v.optional(v.string()),
    apiKey: v.optional(v.string()),
  },
  returns: v.string(),
  handler: async (ctx, args) => {
    // Get conversation history
    const messages = await ctx.runQuery(internal.messages.listInternal, {
      conversationId: args.conversationId,
    });

    // Get GitHub token — env var first, then admin setting
    let githubToken: string | undefined;
    const ghEnv = process.env.GITHUB_TOKEN;
    if (ghEnv && ghEnv.length > 0) {
      githubToken = ghEnv;
    } else {
      try {
        const ghSetting = await ctx.runQuery(
          internal.admin.getSettingInternal,
          { key: "github_token" }
        );
        if (ghSetting) githubToken = ghSetting;
      } catch { /* none */ }
    }

    // Build context with token budget
    const systemTokens = Math.ceil(J_SYSTEM_PROMPT.length / 4);
    const contextBudget = 2800;
    let tokenCount = systemTokens;
    const contextMessages: Array<{ role: string; content: string }> = [];

    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      const msgTokens = Math.ceil(msg.content.length / 4);
      if (tokenCount + msgTokens > contextBudget) break;
      contextMessages.unshift({ role: msg.role, content: msg.content });
    }

    // Resolve providers
    const available = await getAvailableProviders(ctx);

    if (args.apiKey && args.apiKey.length > 0) {
      const groqProvider = PROVIDERS.find((p) => p.name === "groq")!;
      available.unshift({ provider: groqProvider, apiKey: args.apiKey });
    }

    if (available.length === 0) {
      const fallback =
        "⚠️ No LLM provider configured. An admin needs to set a Gemini, Groq, or Cerebras API key in Admin → Settings.";
      await ctx.runMutation(internal.messages.addAssistantMessageInternal, {
        conversationId: args.conversationId,
        content: fallback,
        metadata: { model: "none" },
      });
      return fallback;
    }

    const startTime = Date.now();
    const allToolResults: Array<{
      tool: string;
      args: string;
      result: string;
      status: "success" | "error";
    }> = [];

    // Try each provider in order
    let lastError = "";
    for (const { provider, apiKey } of available) {
      const requestedModel = args.model || "";
      const model = provider.models.includes(requestedModel)
        ? requestedModel
        : provider.defaultModel;

      try {
        let loopMessages: Array<{ role: string; content: string }> = [
          { role: "system", content: J_SYSTEM_PROMPT },
          ...contextMessages,
        ];
        let finalReply = "";
        let toolsUsed = 0;

        for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
          const body: Record<string, unknown> = {
            model,
            messages: loopMessages,
            max_tokens: 1024,
            temperature: 0.7,
            top_p: 0.9,
          };
          // NO tools/tool_choice — J uses text-based ACTION dispatch

          const response = await apiFetch(provider.url, body, apiKey);

          if (!response.ok) {
            const errText = await response.text();
            throw new Error(
              `${provider.name} ${response.status}: ${errText.slice(0, 300)}`
            );
          }

          const data = await response.json();
          const choice = data.choices?.[0];
          const rawReply = choice?.message?.content || "";

          // Parse for ACTION: pattern (mirrors action.py extract_action)
          const action = extractAction(rawReply);

          if (!action || toolsUsed >= J_TOOL_BUDGET) {
            // No action found or budget exhausted — this is the final reply
            finalReply = rawReply;
            break;
          }

          // Execute the tool (pass LLM config for tool_forge)
          toolsUsed++;
          const { result, status } = await executeTool(
            action.tool,
            action.args,
            githubToken,
            { url: provider.url, apiKey, model }
          );

          allToolResults.push({
            tool: action.tool,
            args: JSON.stringify(action.args),
            result: result.slice(0, 2000),
            status,
          });

          // Strip the ACTION from visible text, keep any plan text before it
          const visibleText = stripAction(rawReply);

          // Feed back: assistant message (with ACTION), then tool result
          loopMessages.push({
            role: "assistant",
            content: rawReply,
          });
          loopMessages.push({
            role: "user",
            content: `[TOOL RESULT] ${action.tool} (${status}):\n${result.slice(0, 3000)}`,
          });
        }

        // If no text reply but tools ran, summarize
        if (!finalReply && allToolResults.length > 0) {
          finalReply = allToolResults
            .map((tr) => `🔧 **${tr.tool}** (${tr.status}): ${tr.result.slice(0, 500)}`)
            .join("\n\n");
        }

        // Clean any leftover ACTION: from the final reply
        finalReply = stripAction(finalReply) || finalReply;

        const latencyMs = Date.now() - startTime;
        const providerTag = `${provider.name}/${model}`;

        await ctx.runMutation(internal.messages.addAssistantMessageInternal, {
          conversationId: args.conversationId,
          content: finalReply || "...",
          toolCalls:
            allToolResults.length > 0
              ? allToolResults.map((tr) => ({
                  tool: tr.tool,
                  args: tr.args,
                  result: tr.result.slice(0, 1000),
                  status: tr.status,
                }))
              : undefined,
          metadata: { model: providerTag, latencyMs },
        });

        return finalReply || "...";
      } catch (error: unknown) {
        lastError =
          error instanceof Error ? error.message : String(error);
        continue;
      }
    }

    // All providers exhausted
    const errorReply = `⚠️ All providers failed. Last error: ${lastError}`;
    await ctx.runMutation(internal.messages.addAssistantMessageInternal, {
      conversationId: args.conversationId,
      content: errorReply,
      metadata: { model: "none", latencyMs: Date.now() - startTime },
    });
    return errorReply;
  },
});

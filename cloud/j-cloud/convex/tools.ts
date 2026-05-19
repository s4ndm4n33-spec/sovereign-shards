/**
 * J Cloud — Full Tool Execution Engine
 * Mirrors every tool from the Sovereign Shards repo, adapted for cloud execution.
 * All dev tools operate via GitHub API. tool_forge generates + commits new tools.
 */

// ===================== HELPERS =====================

function ghHeaders(token?: string): Record<string, string> {
  const h: Record<string, string> = {
    Accept: "application/vnd.github.v3+json",
    "User-Agent": "J-Cloud-Agent/1.0",
  };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

function rawHeaders(token?: string): Record<string, string> {
  return {
    ...ghHeaders(token),
    Accept: "application/vnd.github.v3.raw",
  };
}

/** Truncate tool output to keep within context budget */
function truncate(text: string, max = 4000): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + `\n... [truncated, ${text.length} total chars]`;
}

// ===================== GITHUB CORE TOOLS =====================

export async function executeWebSearch(query: string): Promise<string> {
  try {
    const encoded = encodeURIComponent(query);
    const response = await fetch(
      `https://html.duckduckgo.com/html/?q=${encoded}`,
      {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
      }
    );
    if (!response.ok) return `Search failed: HTTP ${response.status}`;
    const html = await response.text();

    const results: Array<{ title: string; url: string; snippet: string }> = [];
    const resultRegex =
      /<a rel="nofollow" class="result__a" href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/g;
    const snippetRegex =
      /<a class="result__snippet"[^>]*>([\s\S]*?)<\/a>/g;
    let match;
    while ((match = resultRegex.exec(html)) !== null && results.length < 5) {
      const url = decodeURIComponent(
        match[1].replace(/\/l\/\?uddg=/, "").split("&")[0]
      );
      const title = match[2].replace(/<[^>]+>/g, "").trim();
      const snippetMatch = snippetRegex.exec(html);
      const snippet = snippetMatch
        ? snippetMatch[1].replace(/<[^>]+>/g, "").trim()
        : "";
      if (title && url) results.push({ title, url, snippet });
    }
    if (results.length === 0) return `No results found for: "${query}"`;
    return results
      .map(
        (r, i) =>
          `${i + 1}. ${r.title}\n   ${r.url}${r.snippet ? `\n   ${r.snippet}` : ""}`
      )
      .join("\n\n");
  } catch (err) {
    return `Search error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

export async function executeGithubListTree(
  owner: string,
  repo: string,
  path: string = "",
  branch: string = "main",
  token?: string
): Promise<string> {
  try {
    const url = path
      ? `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`
      : `https://api.github.com/repos/${owner}/${repo}/git/trees/${branch}?recursive=1`;
    const response = await fetch(url, { headers: ghHeaders(token) });
    if (!response.ok)
      return `GitHub tree error: ${response.status} ${response.statusText}`;
    const data = await response.json();

    if (Array.isArray(data)) {
      return data
        .map(
          (f: { type: string; name: string; path: string; size?: number }) =>
            `${f.type === "dir" ? "📁" : "📄"} ${f.path}${f.size ? ` (${f.size}B)` : ""}`
        )
        .join("\n");
    }
    const tree = data.tree || [];
    const lines = tree
      .slice(0, 200)
      .map(
        (f: { type: string; path: string; size?: number }) =>
          `${f.type === "tree" ? "📁" : "📄"} ${f.path}${f.size ? ` (${f.size}B)` : ""}`
      );
    if (tree.length > 200) lines.push(`... and ${tree.length - 200} more files`);
    return lines.join("\n");
  } catch (err) {
    return `GitHub tree error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

export async function executeGithubReadFile(
  owner: string,
  repo: string,
  path: string,
  branch: string = "main",
  maxLines: number = 0,
  token?: string
): Promise<string> {
  try {
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`,
      { headers: rawHeaders(token) }
    );
    if (!response.ok) {
      if (response.status === 404) return `File not found: ${path}`;
      return `GitHub read error: ${response.status} ${response.statusText}`;
    }
    let content = await response.text();
    if (maxLines > 0) {
      const lines = content.split("\n");
      if (lines.length > maxLines) {
        content = lines.slice(0, maxLines).join("\n") +
          `\n... [${lines.length - maxLines} more lines]`;
      }
    }
    return truncate(content, 10000);
  } catch (err) {
    return `GitHub read error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

export async function executeGithubWriteFile(
  owner: string,
  repo: string,
  path: string,
  content: string,
  message: string,
  branch: string = "main",
  token?: string
): Promise<string> {
  if (!token) return "❌ No GitHub token configured. Add one in Admin → Settings.";
  try {
    let sha: string | undefined;
    const getResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`,
      { headers: ghHeaders(token) }
    );
    if (getResp.ok) {
      sha = (await getResp.json()).sha;
    }

    const encoded = btoa(unescape(encodeURIComponent(content)));
    const body: Record<string, string> = { message, content: encoded, branch };
    if (sha) body.sha = sha;

    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/${path}`,
      {
        method: "PUT",
        headers: ghHeaders(token),
        body: JSON.stringify(body),
      }
    );
    if (!response.ok) {
      const err = await response.text();
      return `❌ Write failed: ${response.status} — ${err.slice(0, 200)}`;
    }
    const result = await response.json();
    return `✅ ${sha ? "Updated" : "Created"} \`${path}\` — commit ${result.commit?.sha?.slice(0, 7)}`;
  } catch (err) {
    return `❌ Write error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

export async function executeGithubMultiCommit(
  owner: string,
  repo: string,
  branch: string = "main",
  message: string,
  files: Array<{ path: string; content?: string; action: string }>,
  token?: string
): Promise<string> {
  if (!token) return "❌ No GitHub token configured. Add one in Admin → Settings.";
  const headers = ghHeaders(token);

  try {
    const refResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/refs/heads/${branch}`,
      { headers }
    );
    if (!refResp.ok)
      return `❌ Branch '${branch}' not found: ${refResp.status}`;
    const refData = await refResp.json();
    const baseCommitSha = refData.object.sha;

    const commitResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/commits/${baseCommitSha}`,
      { headers }
    );
    if (!commitResp.ok) return `❌ Could not read base commit`;
    const commitData = await commitResp.json();
    const baseTreeSha = commitData.tree.sha;

    const treeEntries: Array<{
      path: string;
      mode: string;
      type: string;
      sha: string | null;
    }> = [];

    for (const file of files) {
      if (file.action === "delete") {
        treeEntries.push({
          path: file.path,
          mode: "100644",
          type: "blob",
          sha: null,
        });
      } else {
        const blobResp = await fetch(
          `https://api.github.com/repos/${owner}/${repo}/git/blobs`,
          {
            method: "POST",
            headers,
            body: JSON.stringify({
              content: file.content || "",
              encoding: "utf-8",
            }),
          }
        );
        if (!blobResp.ok) {
          const err = await blobResp.text();
          return `❌ Blob creation failed for ${file.path}: ${err.slice(0, 200)}`;
        }
        const blobData = await blobResp.json();
        treeEntries.push({
          path: file.path,
          mode: "100644",
          type: "blob",
          sha: blobData.sha,
        });
      }
    }

    const treeResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/trees`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          base_tree: baseTreeSha,
          tree: treeEntries,
        }),
      }
    );
    if (!treeResp.ok) {
      const err = await treeResp.text();
      return `❌ Tree creation failed: ${err.slice(0, 200)}`;
    }
    const treeData = await treeResp.json();

    const newCommitResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/commits`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          message,
          tree: treeData.sha,
          parents: [baseCommitSha],
        }),
      }
    );
    if (!newCommitResp.ok) {
      const err = await newCommitResp.text();
      return `❌ Commit creation failed: ${err.slice(0, 200)}`;
    }
    const newCommitData = await newCommitResp.json();

    const updateRefResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/refs/heads/${branch}`,
      {
        method: "PATCH",
        headers,
        body: JSON.stringify({ sha: newCommitData.sha }),
      }
    );
    if (!updateRefResp.ok) {
      const err = await updateRefResp.text();
      return `❌ Ref update failed: ${err.slice(0, 200)}`;
    }

    const created = files.filter((f) => f.action === "create").length;
    const updated = files.filter((f) => f.action === "update").length;
    const deleted = files.filter((f) => f.action === "delete").length;
    const parts = [];
    if (created) parts.push(`${created} created`);
    if (updated) parts.push(`${updated} updated`);
    if (deleted) parts.push(`${deleted} deleted`);

    return `✅ Pushed to \`${branch}\` — commit \`${newCommitData.sha.slice(0, 7)}\`\n${parts.join(", ")} (${files.length} files total)\n${files.map((f) => `  ${f.action === "delete" ? "🗑️" : f.action === "create" ? "➕" : "✏️"} ${f.path}`).join("\n")}`;
  } catch (err) {
    return `❌ Multi-commit error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

export async function executeGithubCreateBranch(
  owner: string,
  repo: string,
  branch: string,
  fromBranch: string = "main",
  token?: string
): Promise<string> {
  if (!token) return "❌ No GitHub token configured. Add one in Admin → Settings.";
  try {
    const refResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/refs/heads/${fromBranch}`,
      { headers: ghHeaders(token) }
    );
    if (!refResp.ok)
      return `❌ Source branch '${fromBranch}' not found`;
    const refData = await refResp.json();

    const createResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/refs`,
      {
        method: "POST",
        headers: ghHeaders(token),
        body: JSON.stringify({
          ref: `refs/heads/${branch}`,
          sha: refData.object.sha,
        }),
      }
    );
    if (!createResp.ok) {
      const err = await createResp.text();
      if (err.includes("Reference already exists"))
        return `⚠️ Branch '${branch}' already exists`;
      return `❌ Branch creation failed: ${err.slice(0, 200)}`;
    }
    return `✅ Branch \`${branch}\` created from \`${fromBranch}\` at ${refData.object.sha.slice(0, 7)}`;
  } catch (err) {
    return `❌ Branch error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

export async function executeGithubCreatePR(
  owner: string,
  repo: string,
  title: string,
  head: string,
  base: string = "main",
  body: string = "",
  token?: string
): Promise<string> {
  if (!token) return "❌ No GitHub token configured. Add one in Admin → Settings.";
  try {
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/pulls`,
      {
        method: "POST",
        headers: ghHeaders(token),
        body: JSON.stringify({ title, head, base, body }),
      }
    );
    if (!response.ok) {
      const err = await response.text();
      return `❌ PR creation failed: ${err.slice(0, 200)}`;
    }
    const pr = await response.json();
    return `✅ PR #${pr.number} created: ${pr.title}\n   ${pr.html_url}`;
  } catch (err) {
    return `❌ PR error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

export async function executeGithubDeleteFile(
  owner: string,
  repo: string,
  path: string,
  message: string,
  branch: string = "main",
  token?: string
): Promise<string> {
  if (!token) return "❌ No GitHub token configured. Add one in Admin → Settings.";
  try {
    const getResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`,
      { headers: ghHeaders(token) }
    );
    if (!getResp.ok) {
      if (getResp.status === 404) return `File not found: ${path}`;
      return `❌ Could not read file: ${getResp.status}`;
    }
    const fileData = await getResp.json();

    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/${path}`,
      {
        method: "DELETE",
        headers: ghHeaders(token),
        body: JSON.stringify({
          message,
          sha: fileData.sha,
          branch,
        }),
      }
    );
    if (!response.ok) {
      const err = await response.text();
      return `❌ Delete failed: ${err.slice(0, 200)}`;
    }
    const result = await response.json();
    return `✅ Deleted \`${path}\` — commit ${result.commit?.sha?.slice(0, 7)}`;
  } catch (err) {
    return `❌ Delete error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

// ===================== DEV TOOLS (Shard equivalents) =====================

/** str_replace — Surgical find-and-replace in a file (mirrors run_str_replace) */
export async function executeStrReplace(
  owner: string,
  repo: string,
  path: string,
  oldStr: string,
  newStr: string,
  branch: string = "main",
  token?: string
): Promise<string> {
  if (!token) return "❌ No GitHub token configured.";
  try {
    // Read current file
    const readResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`,
      { headers: rawHeaders(token) }
    );
    if (!readResp.ok) return `❌ File not found: ${path}`;
    const content = await readResp.text();

    if (!content.includes(oldStr)) {
      return `❌ String not found in ${path}. Make sure the old string matches exactly (including whitespace).`;
    }

    const occurrences = content.split(oldStr).length - 1;
    const newContent = content.replace(oldStr, newStr);

    // Get SHA for update
    const metaResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`,
      { headers: ghHeaders(token) }
    );
    const meta = await metaResp.json();

    const encoded = btoa(unescape(encodeURIComponent(newContent)));
    const writeResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/${path}`,
      {
        method: "PUT",
        headers: ghHeaders(token),
        body: JSON.stringify({
          message: `str_replace in ${path}`,
          content: encoded,
          sha: meta.sha,
          branch,
        }),
      }
    );
    if (!writeResp.ok) {
      const err = await writeResp.text();
      return `❌ Write failed: ${err.slice(0, 200)}`;
    }
    const result = await writeResp.json();
    return `✅ Replaced ${occurrences} occurrence(s) in \`${path}\` — commit ${result.commit?.sha?.slice(0, 7)}`;
  } catch (err) {
    return `❌ str_replace error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

/** search_code — Search for text patterns in repo files (mirrors run_search) */
export async function executeSearchCode(
  owner: string,
  repo: string,
  pattern: string,
  path: string = "",
  ext: string = "",
  token?: string
): Promise<string> {
  try {
    // Use GitHub code search API
    let q = `${pattern} repo:${owner}/${repo}`;
    if (path) q += ` path:${path}`;
    if (ext) q += ` extension:${ext}`;

    const response = await fetch(
      `https://api.github.com/search/code?q=${encodeURIComponent(q)}&per_page=20`,
      { headers: ghHeaders(token) }
    );
    if (!response.ok) {
      // Fallback: search by reading tree and files
      return await searchByTreeWalk(owner, repo, pattern, path, ext, token);
    }
    const data = await response.json();
    if (!data.items || data.items.length === 0) {
      return `No matches for "${pattern}"${path ? ` in ${path}` : ""}`;
    }

    const lines = [`Found ${data.total_count} match(es) for "${pattern}":\n`];
    for (const item of data.items.slice(0, 15)) {
      lines.push(`📄 ${item.path}`);
      if (item.text_matches) {
        for (const tm of item.text_matches.slice(0, 2)) {
          lines.push(`   ${tm.fragment?.slice(0, 150)}`);
        }
      }
    }
    if (data.total_count > 15) {
      lines.push(`\n... and ${data.total_count - 15} more matches`);
    }
    return lines.join("\n");
  } catch (err) {
    return `Search error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

/** Fallback search — walk tree and grep files */
async function searchByTreeWalk(
  owner: string,
  repo: string,
  pattern: string,
  path: string,
  ext: string,
  token?: string
): Promise<string> {
  try {
    const treeResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/trees/main?recursive=1`,
      { headers: ghHeaders(token) }
    );
    if (!treeResp.ok) return `❌ Could not read repo tree`;
    const treeData = await treeResp.json();
    const files = (treeData.tree || []).filter(
      (f: { type: string; path: string; size?: number }) => {
        if (f.type !== "blob") return false;
        if (path && !f.path.startsWith(path)) return false;
        if (ext && !f.path.endsWith(`.${ext}`)) return false;
        if ((f.size || 0) > 100000) return false; // Skip large files
        return /\.(py|ts|js|json|md|txt|toml|yml|yaml|cfg|ini|sh|bat|rs|go|java|c|h|cpp)$/.test(f.path);
      }
    );

    const matches: Array<{ file: string; lines: string[] }> = [];
    const lowerPattern = pattern.toLowerCase();

    // Check up to 50 files
    for (const f of files.slice(0, 50)) {
      try {
        const resp = await fetch(
          `https://api.github.com/repos/${owner}/${repo}/contents/${f.path}?ref=main`,
          { headers: rawHeaders(token) }
        );
        if (!resp.ok) continue;
        const content = await resp.text();
        const fileLines = content.split("\n");
        const matchingLines: string[] = [];
        for (let i = 0; i < fileLines.length; i++) {
          if (fileLines[i].toLowerCase().includes(lowerPattern)) {
            matchingLines.push(`  L${i + 1}: ${fileLines[i].trim().slice(0, 120)}`);
          }
        }
        if (matchingLines.length > 0) {
          matches.push({ file: f.path, lines: matchingLines.slice(0, 5) });
        }
      } catch {
        continue;
      }
      if (matches.length >= 15) break;
    }

    if (matches.length === 0) return `No matches for "${pattern}"`;
    const output = [`Found matches for "${pattern}":\n`];
    for (const m of matches) {
      output.push(`📄 ${m.file}`);
      output.push(...m.lines);
    }
    return output.join("\n");
  } catch (err) {
    return `Search error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

/** list_commits — Git log equivalent (mirrors run_git log) */
export async function executeListCommits(
  owner: string,
  repo: string,
  branch: string = "main",
  count: number = 10,
  path: string = "",
  token?: string
): Promise<string> {
  try {
    let url = `https://api.github.com/repos/${owner}/${repo}/commits?sha=${branch}&per_page=${Math.min(count, 30)}`;
    if (path) url += `&path=${encodeURIComponent(path)}`;

    const response = await fetch(url, { headers: ghHeaders(token) });
    if (!response.ok) return `❌ Commits error: ${response.status}`;
    const commits = await response.json();

    if (!commits.length) return "No commits found.";
    return commits
      .map(
        (c: any) =>
          `${c.sha.slice(0, 7)} ${c.commit.message.split("\n")[0].slice(0, 80)} (${c.commit.author?.name || "?"}, ${c.commit.author?.date?.slice(0, 10) || "?"})`
      )
      .join("\n");
  } catch (err) {
    return `Commits error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

/** diff — Compare two commits or branches (mirrors run_git diff) */
export async function executeGithubDiff(
  owner: string,
  repo: string,
  base: string,
  head: string = "main",
  token?: string
): Promise<string> {
  try {
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/compare/${base}...${head}`,
      { headers: ghHeaders(token) }
    );
    if (!response.ok) return `❌ Diff error: ${response.status}`;
    const data = await response.json();

    const summary = [
      `Comparing \`${base}\` → \`${head}\`: ${data.total_commits} commit(s), ${data.files?.length || 0} file(s) changed\n`,
    ];
    if (data.files) {
      for (const f of data.files.slice(0, 30)) {
        const icon = f.status === "added" ? "➕" : f.status === "removed" ? "🗑️" : "✏️";
        summary.push(
          `${icon} ${f.filename} (+${f.additions} -${f.deletions})`
        );
      }
      if (data.files.length > 30) {
        summary.push(`... and ${data.files.length - 30} more files`);
      }
    }
    return summary.join("\n");
  } catch (err) {
    return `Diff error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

/** scaffold — Create a package directory with __init__.py (mirrors run_scaffold) */
export async function executeScaffold(
  owner: string,
  repo: string,
  name: string,
  branch: string = "main",
  token?: string
): Promise<string> {
  if (!token) return "❌ No GitHub token configured.";
  const initContent = `# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.\n"""${name} package."""\n`;
  return await executeGithubWriteFile(
    owner, repo, `${name}/__init__.py`, initContent,
    `scaffold: create ${name} package`, branch, token
  );
}

/** calc — Safe calculator (mirrors run_calc) */
export function executeCalc(expression: string): string {
  try {
    // Natural language → math
    let expr = expression.toLowerCase().trim()
      .replace(/\bplus\b|added to/g, "+")
      .replace(/\bminus\b|subtracted from/g, "-")
      .replace(/\btimes\b|multiplied by/g, "*")
      .replace(/\bdivided by\b/g, "/")
      .replace(/\bwhat is\b|\bcalculate\b/g, "")
      .replace(/\bsqrt\(([^)]+)\)/g, (_, n) => String(Math.sqrt(parseFloat(n))))
      .replace(/\babs\(([^)]+)\)/g, (_, n) => String(Math.abs(parseFloat(n))))
      .replace(/\bround\(([^)]+)\)/g, (_, n) => String(Math.round(parseFloat(n))))
      .replace(/\bpi\b/g, String(Math.PI))
      .replace(/\be\b/g, String(Math.E))
      .replace(/\*\*/g, "^")
      .trim();

    // Validate: only allow digits, operators, parens, dots, spaces, ^
    if (!/^[\d+\-*/().^ \t]+$/.test(expr)) {
      return `[CALC ERROR] Invalid expression: ${expression}`;
    }

    // Handle power
    expr = expr.replace(/(\d+\.?\d*)\^(\d+\.?\d*)/g, (_, a, b) =>
      String(Math.pow(parseFloat(a), parseFloat(b)))
    );

    // Safe eval using Function (no access to globals)
    const result = new Function(`return (${expr})`)();
    if (typeof result !== "number" || !isFinite(result)) {
      return `[CALC ERROR] Result is not a finite number`;
    }
    return `${expression} = ${result}`;
  } catch (err) {
    return `[CALC ERROR] ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

/** codebase_stats — LOC, file count, language breakdown (mirrors run_stats) */
export async function executeCodebaseStats(
  owner: string,
  repo: string,
  path: string = "",
  branch: string = "main",
  token?: string
): Promise<string> {
  try {
    const treeResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/git/trees/${branch}?recursive=1`,
      { headers: ghHeaders(token) }
    );
    if (!treeResp.ok) return `❌ Stats error: ${treeResp.status}`;
    const treeData = await treeResp.json();
    const files = (treeData.tree || []).filter(
      (f: { type: string; path: string }) => {
        if (f.type !== "blob") return false;
        if (path && !f.path.startsWith(path)) return false;
        return true;
      }
    );

    // Group by extension
    const extCounts: Record<string, { count: number; bytes: number }> = {};
    let totalFiles = 0;
    let totalBytes = 0;

    for (const f of files) {
      totalFiles++;
      const size = (f as any).size || 0;
      totalBytes += size;
      const ext = f.path.split(".").pop()?.toLowerCase() || "other";
      if (!extCounts[ext]) extCounts[ext] = { count: 0, bytes: 0 };
      extCounts[ext].count++;
      extCounts[ext].bytes += size;
    }

    const dirs = new Set(
      files.map((f: { path: string }) => f.path.split("/").slice(0, -1).join("/")).filter(Boolean)
    );

    const sorted = Object.entries(extCounts).sort((a, b) => b[1].count - a[1].count);
    const lines = [
      `📊 Codebase Stats${path ? ` (${path})` : ""}`,
      `Files: ${totalFiles} | Dirs: ${dirs.size} | Total: ${(totalBytes / 1024).toFixed(1)} KB\n`,
      "By extension:",
    ];
    for (const [ext, data] of sorted.slice(0, 20)) {
      lines.push(`  .${ext}: ${data.count} files (${(data.bytes / 1024).toFixed(1)} KB)`);
    }
    return lines.join("\n");
  } catch (err) {
    return `Stats error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

/** list_issues — GitHub issue tracker (no shard equivalent — cloud bonus) */
export async function executeListIssues(
  owner: string,
  repo: string,
  state: string = "open",
  count: number = 10,
  token?: string
): Promise<string> {
  try {
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/issues?state=${state}&per_page=${Math.min(count, 30)}`,
      { headers: ghHeaders(token) }
    );
    if (!response.ok) return `❌ Issues error: ${response.status}`;
    const issues = await response.json();
    if (!issues.length) return `No ${state} issues found.`;
    return issues
      .filter((i: any) => !i.pull_request) // Exclude PRs
      .map(
        (i: any) =>
          `#${i.number} [${i.state}] ${i.title}${i.labels?.length ? ` (${i.labels.map((l: any) => l.name).join(", ")})` : ""}`
      )
      .join("\n");
  } catch (err) {
    return `Issues error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

/** create_issue — GitHub issue creation */
export async function executeCreateIssue(
  owner: string,
  repo: string,
  title: string,
  body: string = "",
  labels: string[] = [],
  token?: string
): Promise<string> {
  if (!token) return "❌ No GitHub token configured.";
  try {
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/issues`,
      {
        method: "POST",
        headers: ghHeaders(token),
        body: JSON.stringify({ title, body, labels }),
      }
    );
    if (!response.ok) {
      const err = await response.text();
      return `❌ Issue creation failed: ${err.slice(0, 200)}`;
    }
    const issue = await response.json();
    return `✅ Issue #${issue.number} created: ${issue.title}\n   ${issue.html_url}`;
  } catch (err) {
    return `❌ Issue error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

/** dispatch_workflow — Trigger a GitHub Actions workflow (for run_test equivalent) */
export async function executeDispatchWorkflow(
  owner: string,
  repo: string,
  workflow: string = "ci.yml",
  branch: string = "main",
  token?: string
): Promise<string> {
  if (!token) return "❌ No GitHub token configured.";
  try {
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`,
      {
        method: "POST",
        headers: ghHeaders(token),
        body: JSON.stringify({ ref: branch }),
      }
    );
    if (!response.ok) {
      const err = await response.text();
      return `❌ Workflow dispatch failed: ${response.status} — ${err.slice(0, 200)}`;
    }
    return `✅ Triggered workflow \`${workflow}\` on \`${branch}\`. Check Actions tab for results.`;
  } catch (err) {
    return `❌ Dispatch error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

// ===================== TOOL FORGE =====================
// The crown jewel — generates, validates, and commits new tools to the repo.
// Mirrors app/agent/tool_forge.py + app/agent/tool_researcher.py

const TOOL_TEMPLATE = `\
# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Auto-generated tool: {PURPOSE}

Built by J's tool forge.  Follows the standard tool contract:
TOOL_NAME, TOOL_DESC, and a run() function that returns a string.
"""

import os
import sys

TOOL_NAME = "run_{TOOL_NAME}"
TOOL_DESC = """{PURPOSE}"""

{IMPLEMENTATION}


# ── CLI entry point (tools/run convention) ───────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        print(run(*args))
    except Exception as exc:
        print(f"[TOOL ERROR] {{exc}}")
        sys.exit(1)
`;

/**
 * tool_forge — Generate a new tool, assemble it, and commit to the repo.
 * Uses the active LLM provider to generate the implementation.
 */
export async function executeToolForge(
  owner: string,
  repo: string,
  name: string,
  purpose: string,
  inputs: string[],
  outputs: string[],
  dependencies: string[],
  branch: string = "main",
  token?: string,
  llmConfig?: { url: string; apiKey: string; model: string }
): Promise<string> {
  if (!token) return "❌ No GitHub token configured.";
  if (!llmConfig) return "❌ No LLM provider available for code generation.";

  try {
    // 1. Build the forge prompt (mirrors build_forge_prompt from tool_forge.py)
    const argsSig = inputs.map((a) => a.split(":")[0].trim()).join(", ");
    const depNote = dependencies.length > 0
      ? `These non-stdlib packages are allowed: ${dependencies.join(", ")}. If any are unavailable, degrade gracefully.`
      : "No non-stdlib packages allowed.";

    const forgePrompt = `Write the Python implementation for this tool. Follow these rules EXACTLY:

1. Define a function: def run(${argsSig}) -> str:
2. The function MUST return a string (the tool output).
3. Use ONLY Python stdlib. ${depNote}
4. Handle errors gracefully — return "[TOOL ERROR] ..." on failure.
5. Do NOT import anything outside stdlib unless listed in dependencies.
6. Do NOT print anything inside run() — return the result string.
7. Keep it under 80 lines. Lean and correct.

Tool spec:
  Name: ${name}
  Purpose: ${purpose}
  Inputs: ${inputs.join(", ") || "none"}
  Outputs: ${outputs.join(", ") || "result string"}

THE FIVE MASTERS APPLY:
- KOROTKEVICH: Efficient code, no waste
- TORVALDS: Proper error handling, no bare except
- CARMACK: No mutable defaults, no deep nesting
- HAMILTON: Every I/O guarded with try/except
- RITCHIE: snake_case, clear names, functions <60 lines

Respond with ONLY the Python code for the run() function and any helper
functions it needs. No imports of os/sys (already at top). No class
definitions. No markdown fences. Just the raw Python.`;

    // 2. Call the LLM to generate the implementation
    const llmResponse = await fetch(llmConfig.url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${llmConfig.apiKey}`,
      },
      body: JSON.stringify({
        model: llmConfig.model,
        messages: [
          { role: "system", content: "You are a Python tool generator. Output ONLY raw Python code. No markdown. No explanation." },
          { role: "user", content: forgePrompt },
        ],
        max_tokens: 800,
        temperature: 0.3,
      }),
    });

    if (!llmResponse.ok) {
      const err = await llmResponse.text();
      return `❌ Forge LLM call failed: ${llmResponse.status} — ${err.slice(0, 200)}`;
    }

    const llmData = await llmResponse.json();
    let implementation = llmData.choices?.[0]?.message?.content || "";

    // Strip markdown fences if model included them
    implementation = implementation
      .replace(/```python?\s*/g, "")
      .replace(/```/g, "")
      .trim();

    if (!implementation || !implementation.includes("def run(")) {
      return `❌ Forge failed: LLM did not generate a valid run() function. Raw output:\n${implementation.slice(0, 300)}`;
    }

    // 3. Assemble the full tool file
    const toolCode = TOOL_TEMPLATE
      .replace("{TOOL_NAME}", name)
      .replace(/{PURPOSE}/g, purpose)
      .replace("{IMPLEMENTATION}", implementation);

    // 4. Read current registry.json
    const regResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/tools/run/registry.json?ref=${branch}`,
      { headers: rawHeaders(token) }
    );
    let registry: Record<string, any> = {};
    if (regResp.ok) {
      try {
        registry = JSON.parse(await regResp.text());
      } catch { /* start fresh */ }
    }

    // Build registry entry
    const registryEntry: Record<string, any> = {
      description: purpose,
      args: inputs.map((inp) => {
        const parts = inp.split(":");
        const argName = parts[0].trim();
        const argType = parts.length > 1 ? parts[1].trim() : "str";
        return { name: argName, type: argType, required: true };
      }),
      side_effect: "exec",
    };
    if (dependencies.length > 0) {
      registryEntry.dependencies = dependencies;
    }

    registry[`run_${name}`] = registryEntry;

    // 5. Commit both files atomically
    const commitResult = await executeGithubMultiCommit(
      owner, repo, branch,
      `forge: add run_${name} — ${purpose}`,
      [
        {
          path: `tools/run/${name}.py`,
          content: toolCode,
          action: "create",
        },
        {
          path: "tools/run/registry.json",
          content: JSON.stringify(registry, null, 2) + "\n",
          action: "update",
        },
      ],
      token
    );

    if (commitResult.startsWith("❌")) return commitResult;

    return `🔨 TOOL FORGED: \`run_${name}\`\n\n` +
      `Purpose: ${purpose}\n` +
      `Args: ${inputs.join(", ") || "none"}\n` +
      `File: tools/run/${name}.py\n` +
      `Registry: updated\n\n` +
      commitResult + "\n\n" +
      `Generated implementation:\n\`\`\`python\n${implementation.slice(0, 1500)}\n\`\`\``;

  } catch (err) {
    return `❌ Forge error: ${err instanceof Error ? err.message : "Unknown"}`;
  }
}

// ===================== TOOL DISPATCHER =====================

export async function executeTool(
  name: string,
  args: Record<string, unknown>,
  githubToken?: string,
  llmConfig?: { url: string; apiKey: string; model: string }
): Promise<{ result: string; status: "success" | "error" }> {
  // Default repo context
  const owner = (args.owner as string) || "s4ndm4n33-spec";
  const repo = (args.repo as string) || "sovereign-shards";
  const branch = (args.branch as string) || "main";

  try {
    let result: string;
    switch (name) {
      // --- Core GitHub tools ---
      case "web_search":
        result = await executeWebSearch(args.query as string);
        break;
      case "github_list_tree":
      case "run_tree":
        result = await executeGithubListTree(
          owner, repo,
          (args.path as string) || "",
          branch, githubToken
        );
        break;
      case "github_read_file":
      case "run_read":
        result = await executeGithubReadFile(
          owner, repo,
          args.path as string,
          branch,
          parseInt(String(args.max_lines || "0")) || 0,
          githubToken
        );
        break;
      case "github_write_file":
      case "run_write":
        result = await executeGithubWriteFile(
          owner, repo,
          args.path as string,
          args.content as string,
          (args.message as string) || `Update ${args.path}`,
          branch, githubToken
        );
        break;
      case "github_multi_commit":
        result = await executeGithubMultiCommit(
          owner, repo, branch,
          args.message as string,
          args.files as Array<{ path: string; content?: string; action: string }>,
          githubToken
        );
        break;
      case "github_create_branch":
        result = await executeGithubCreateBranch(
          owner, repo,
          args.branch as string,
          (args.from_branch as string) || "main",
          githubToken
        );
        break;
      case "github_create_pr":
        result = await executeGithubCreatePR(
          owner, repo,
          args.title as string,
          args.head as string,
          (args.base as string) || "main",
          (args.body as string) || "",
          githubToken
        );
        break;
      case "github_delete_file":
        result = await executeGithubDeleteFile(
          owner, repo,
          args.path as string,
          args.message as string,
          branch, githubToken
        );
        break;

      // --- Dev tools (shard equivalents) ---
      case "str_replace":
      case "run_str_replace":
        result = await executeStrReplace(
          owner, repo,
          args.path as string,
          args.old as string,
          args.new as string,
          branch, githubToken
        );
        break;
      case "search_code":
      case "run_search":
        result = await executeSearchCode(
          owner, repo,
          args.pattern as string,
          (args.path as string) || "",
          (args.ext as string) || "",
          githubToken
        );
        break;
      case "list_commits":
      case "run_git":
        result = await executeListCommits(
          owner, repo, branch,
          parseInt(String(args.count || "10")) || 10,
          (args.path as string) || "",
          githubToken
        );
        break;
      case "github_diff":
        result = await executeGithubDiff(
          owner, repo,
          args.base as string,
          (args.head as string) || "main",
          githubToken
        );
        break;
      case "scaffold":
      case "run_scaffold":
        result = await executeScaffold(
          owner, repo,
          args.name as string,
          branch, githubToken
        );
        break;
      case "calc":
      case "run_calc":
        result = executeCalc(args.expression as string);
        break;
      case "codebase_stats":
      case "run_stats":
        result = await executeCodebaseStats(
          owner, repo,
          (args.path as string) || "",
          branch, githubToken
        );
        break;
      case "list_issues":
        result = await executeListIssues(
          owner, repo,
          (args.state as string) || "open",
          parseInt(String(args.count || "10")) || 10,
          githubToken
        );
        break;
      case "create_issue":
        result = await executeCreateIssue(
          owner, repo,
          args.title as string,
          (args.body as string) || "",
          (args.labels as string[]) || [],
          githubToken
        );
        break;
      case "dispatch_workflow":
      case "run_test":
        result = await executeDispatchWorkflow(
          owner, repo,
          (args.workflow as string) || "ci.yml",
          branch, githubToken
        );
        break;

      // --- Tool Forge ---
      case "tool_forge":
        result = await executeToolForge(
          owner, repo,
          args.name as string,
          args.purpose as string,
          (args.inputs as string[]) || [],
          (args.outputs as string[]) || [],
          (args.dependencies as string[]) || [],
          branch, githubToken, llmConfig
        );
        break;

      default:
        return { result: `Unknown tool: ${name}. Use github_list_tree to see available tools, or tool_forge to create a new one.`, status: "error" };
    }
    return { result, status: "success" };
  } catch (err) {
    return {
      result: `Tool error: ${err instanceof Error ? err.message : "Unknown"}`,
      status: "error",
    };
  }
}

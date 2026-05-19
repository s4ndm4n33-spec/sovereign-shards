import { type ChildProcess, spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createPageHelper } from "./auth";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");

const PREVIEW_PORT = 4173;
const PREVIEW_URL = `http://localhost:${PREVIEW_PORT}`;
const MAX_WAIT_MS = 30000;
const POLL_INTERVAL_MS = 500;

async function waitForServer(url: string, maxWait: number): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    try {
      const response = await fetch(url);
      if (response.ok || response.status === 304) {
        return true;
      }
    } catch {
      // Server not ready yet
    }
    await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
  }
  return false;
}

function startPreviewServer(): ChildProcess {
  const server = spawn("bun", ["run", "preview"], {
    cwd: projectRoot,
    stdio: ["ignore", "pipe", "pipe"],
    detached: false,
  });

  server.stdout?.on("data", () => {});
  server.stderr?.on("data", () => {});

  return server;
}

async function main() {
  const args = process.argv.slice(2);
  const path = args[0] || "/";
  const filename = args[1] || `screenshot-${Date.now()}.png`;

  console.log("🚀 Starting preview server...");
  const server = startPreviewServer();

  try {
    console.log(`⏳ Waiting for server at ${PREVIEW_URL}...`);
    const ready = await waitForServer(PREVIEW_URL, MAX_WAIT_MS);

    if (!ready) {
      console.error(
        "❌ Server failed to start. Run 'bun run sync:build' first.",
      );
      process.exit(1);
    }

    console.log(`📸 Taking screenshot of ${path}...\n`);

    process.env.APP_URL = PREVIEW_URL;
    const helper = await createPageHelper();

    await helper.goto(path);
    await helper.screenshot(filename);

    console.log(`\n📍 URL: ${helper.page.url()}`);
    await helper.printPageContent();
    helper.printConsoleLogs();

    await helper.close();
    console.log("\n✅ Done!");
  } finally {
    server.kill("SIGTERM");
  }
}

main().catch(err => {
  console.error("Failed:", err);
  process.exit(1);
});

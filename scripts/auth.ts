import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, statSync, unlinkSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { Browser, BrowserContext, ConsoleMessage, Page } from "playwright";
import { chromium } from "playwright";
import { TEST_USER } from "./testUser";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TMP_DIR = join(__dirname, "..", "tmp");

const AUTH_STATE_MAX_AGE_MINUTES = 50;

function getAppUrl(): string {
  return process.env.APP_URL || "http://localhost:5173";
}

function getTestId(): string {
  const scriptPath = process.argv[1] || "default";
  const name = basename(scriptPath, ".ts");
  const hash = createHash("md5").update(scriptPath).digest("hex").slice(0, 8);
  return `${name}-${hash}`;
}

function getAuthStatePath(): string {
  return join(TMP_DIR, `auth-state-${getTestId()}.json`);
}

export interface ConsoleLog {
  type: string;
  text: string;
  timestamp: Date;
  location?: string;
}

export interface PageDebugInfo {
  url: string;
  title: string;
  content: string;
  consoleLogs: ConsoleLog[];
}

export class PageHelper {
  private consoleLogs: ConsoleLog[] = [];
  private consoleHandler: ((msg: ConsoleMessage) => void) | null = null;

  constructor(
    public readonly page: Page,
    public readonly browser: Browser,
    public readonly context: BrowserContext,
  ) {
    this.setupConsoleCapture();
  }

  private setupConsoleCapture(): void {
    this.consoleHandler = (msg: ConsoleMessage) => {
      this.consoleLogs.push({
        type: msg.type(),
        text: msg.text(),
        timestamp: new Date(),
        location: msg.location().url,
      });
    };
    this.page.on("console", this.consoleHandler);
  }

  getConsoleLogs(): ConsoleLog[] {
    return [...this.consoleLogs];
  }

  clearConsoleLogs(): void {
    this.consoleLogs = [];
  }

  printConsoleLogs(): void {
    if (this.consoleLogs.length === 0) {
      console.log("\n📋 Console Logs: (none)\n");
      return;
    }
    console.log("\n📋 Console Logs:");
    console.log("─".repeat(60));
    for (const log of this.consoleLogs) {
      const icon =
        log.type === "error" ? "❌" : log.type === "warning" ? "⚠️" : "  ";
      console.log(`${icon} [${log.type.toUpperCase()}] ${log.text}`);
    }
    console.log("─".repeat(60));
  }

  async getPageContent(): Promise<string> {
    return await this.page.locator("body").innerText();
  }

  async printPageContent(): Promise<void> {
    const content = await this.getPageContent();
    console.log("\n📄 Page Content:");
    console.log("─".repeat(60));
    console.log(content || "(empty)");
    console.log("─".repeat(60));
  }

  async getDebugInfo(): Promise<PageDebugInfo> {
    return {
      url: this.page.url(),
      title: await this.page.title(),
      content: await this.getPageContent(),
      consoleLogs: this.getConsoleLogs(),
    };
  }

  async printDebugInfo(): Promise<void> {
    const info = await this.getDebugInfo();
    console.log("\n🔍 Debug Info:");
    console.log("─".repeat(60));
    console.log(`URL: ${info.url}`);
    console.log(`Title: ${info.title}`);
    console.log("─".repeat(60));
    await this.printPageContent();
    this.printConsoleLogs();
  }

  async screenshot(name?: string): Promise<string> {
    await mkdir(TMP_DIR, { recursive: true });
    const filename = name || `screenshot-${Date.now()}.png`;
    const path = join(TMP_DIR, filename);
    await this.page.screenshot({ path, fullPage: true });
    console.log(`📸 Screenshot saved: ${path}`);
    return path;
  }

  async goto(path: string): Promise<void> {
    const url = path.startsWith("http") ? path : `${getAppUrl()}${path}`;
    await this.page.goto(url, { waitUntil: "networkidle" });
  }

  async close(): Promise<void> {
    await this.browser.close();
  }
}

async function isAuthenticated(page: Page): Promise<boolean> {
  // If we're on /login or /signup, we're not authenticated
  const url = page.url();
  return !url.includes("/login") && !url.includes("/signup");
}

export async function ensureTestUserExists(page: Page): Promise<void> {
  await page.goto(`${getAppUrl()}/signup`, { waitUntil: "networkidle" });

  if (await isAuthenticated(page)) {
    console.log("[Auth] Already logged in");
    return;
  }

  const nameInput = page.locator("input[name='name']");
  const hasNameField = await nameInput.isVisible().catch(() => false);

  if (hasNameField) {
    console.log("[Auth] Creating test user account...");
    await nameInput.fill(TEST_USER.name);
    await page.locator("input[name='email']").fill(TEST_USER.email);
    await page.locator("input[name='password']").fill(TEST_USER.password);
    await page.locator("button[type='submit']").click();
    await page.waitForTimeout(1000);

    if (await isAuthenticated(page)) {
      console.log("[Auth] Test user created and logged in");
      return;
    }

    const errorVisible = await page
      .locator("text=Could not create account")
      .isVisible()
      .catch(() => false);
    if (errorVisible) {
      console.log("[Auth] Account may already exist, trying sign in...");
    }
  }

  await signInTestUser(page);
}

export async function signInTestUser(page: Page): Promise<void> {
  await page.goto(`${getAppUrl()}/login`, { waitUntil: "networkidle" });

  if (await isAuthenticated(page)) {
    console.log("[Auth] Already logged in");
    return;
  }

  console.log("[Auth] Signing in as test user...");
  await page.locator("input[name='email']").fill(TEST_USER.email);
  await page.locator("input[name='password']").fill(TEST_USER.password);
  await page.locator("button[type='submit']").click();

  await page.waitForTimeout(3000);

  if (!(await isAuthenticated(page))) {
    console.log("[Auth] Refreshing page to check auth state...");
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
  }

  if (await isAuthenticated(page)) {
    console.log("[Auth] Signed in successfully");
  } else {
    await mkdir(TMP_DIR, { recursive: true });
    await page.screenshot({ path: join(TMP_DIR, "auth-debug.png") });
    const content = await page.locator("body").innerText();
    console.log("[Auth] Page content after sign-in attempt:", content);
    throw new Error("Failed to sign in - Dashboard not visible");
  }
}

export async function saveAuthState(page: Page): Promise<void> {
  await mkdir(TMP_DIR, { recursive: true });
  const authStatePath = getAuthStatePath();
  const context = page.context();
  await context.storageState({ path: authStatePath });
  console.log(`[Auth] Auth state saved to ${authStatePath}`);
}

export async function loadAuthState(): Promise<string | undefined> {
  const authStatePath = getAuthStatePath();

  if (!existsSync(authStatePath)) {
    return undefined;
  }

  try {
    const stats = statSync(authStatePath);
    const ageMinutes = (Date.now() - stats.mtimeMs) / 1000 / 60;

    if (ageMinutes > AUTH_STATE_MAX_AGE_MINUTES) {
      console.log(
        `[Auth] Auth state expired (${ageMinutes.toFixed(0)}m old, max ${AUTH_STATE_MAX_AGE_MINUTES}m), will re-authenticate`,
      );
      unlinkSync(authStatePath);
      return undefined;
    }

    console.log(
      `[Auth] Loading auth state from ${authStatePath} (${ageMinutes.toFixed(0)}m old)`,
    );
    return authStatePath;
  } catch {
    return undefined;
  }
}

export function clearAllAuthStates(): void {
  if (!existsSync(TMP_DIR)) return;

  const files = readdirSync(TMP_DIR);
  let cleared = 0;

  for (const file of files) {
    if (file.startsWith("auth-state-") && file.endsWith(".json")) {
      try {
        unlinkSync(join(TMP_DIR, file));
        cleared++;
      } catch {}
    }
  }

  if (cleared > 0) {
    console.log(`[Auth] Cleared ${cleared} auth state file(s)`);
  }
}

export async function createAuthenticatedBrowser(): Promise<{
  browser: Browser;
  page: Page;
}> {
  const storageState = await loadAuthState();
  const browser = await chromium.launch();
  const context = await browser.newContext(
    storageState ? { storageState } : {},
  );
  const page = await context.newPage();

  // Check auth by going to login - if we get redirected, we're authenticated
  await page.goto(`${getAppUrl()}/login`, { waitUntil: "networkidle" });

  if (!(await isAuthenticated(page))) {
    await ensureTestUserExists(page);
    await saveAuthState(page);
  }

  return { browser, page };
}

export async function createPageHelper(): Promise<PageHelper> {
  const storageState = await loadAuthState();
  const browser = await chromium.launch();
  const context = await browser.newContext(
    storageState ? { storageState } : {},
  );
  const page = await context.newPage();

  const helper = new PageHelper(page, browser, context);

  // Check auth by going to login - if we stay on login, we need to authenticate
  await page.goto(`${getAppUrl()}/login`, { waitUntil: "networkidle" });

  if (!(await isAuthenticated(page))) {
    // Not authenticated - log in
    await ensureTestUserExists(page);
    await saveAuthState(page);
  }

  // Navigate to root - test can go wherever it needs from here
  await page.goto(`${getAppUrl()}/`, { waitUntil: "networkidle" });

  return helper;
}

async function fetchConvexLogs(maxLines = 30): Promise<string> {
  return new Promise(resolve => {
    const logs: string[] = [];
    const proc = spawn(
      "bunx",
      ["convex", "logs", "--history", String(maxLines), "--success"],
      {
        stdio: ["ignore", "pipe", "pipe"],
        cwd: `${dirname(fileURLToPath(import.meta.url))}/..`,
      },
    );

    proc.stdout.on("data", (data: Buffer) => {
      const text = data.toString();
      for (const line of text.split("\n")) {
        if (line.trim() && !line.startsWith("Watching logs")) {
          logs.push(line);
        }
      }
    });

    proc.stderr.on("data", (data: Buffer) => {
      const text = data.toString();
      if (
        !text.includes("WebSocket") &&
        !text.includes("Attempting reconnect")
      ) {
        logs.push(`[stderr] ${text.trim()}`);
      }
    });

    const timeout = setTimeout(() => {
      proc.kill("SIGTERM");
      resolve(logs.length > 0 ? logs.join("\n") : "(No recent log entries)");
    }, 5000);

    proc.on("close", () => {
      clearTimeout(timeout);
      resolve(logs.length > 0 ? logs.join("\n") : "(No recent log entries)");
    });

    proc.on("error", () => {
      clearTimeout(timeout);
      resolve("(Failed to fetch Convex logs)");
    });
  });
}

export async function runTest(
  testName: string,
  testFn: (helper: PageHelper) => Promise<void>,
): Promise<void> {
  console.log(`\n🧪 Running: ${testName}\n`);

  const helper = await createPageHelper();

  try {
    await testFn(helper);
    console.log(`\n✅ ${testName} PASSED\n`);
  } catch (error) {
    console.error(`\n❌ ${testName} FAILED\n`);
    console.error("Error:", error instanceof Error ? error.message : error);

    try {
      await helper.screenshot(`error-${Date.now()}.png`);
      await helper.printDebugInfo();

      console.log("\n🔧 Convex Backend Logs:");
      console.log("─".repeat(60));
      const convexLogs = await fetchConvexLogs();
      console.log(convexLogs);
      console.log("─".repeat(60));
    } catch (debugError) {
      console.error("Failed to capture debug info:", debugError);
    }

    throw error;
  } finally {
    try {
      await saveAuthState(helper.page);
    } catch {}
    await helper.close();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  (async () => {
    console.log("Setting up test user authentication...");
    const helper = await createPageHelper();
    console.log("Test user is ready!");
    await helper.printDebugInfo();
    await helper.close();
  })().catch(console.error);
}

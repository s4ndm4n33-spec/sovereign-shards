import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const envVarName = process.argv[2];

if (!envVarName) {
  console.error("Usage: npx tsx scripts/getEnv.ts <ENV_VAR_NAME>");
  process.exit(1);
}

async function getFromConvex(varName: string): Promise<string | null> {
  return new Promise(resolve => {
    const proc = spawn("npx", ["convex", "env", "get", varName], {
      stdio: ["ignore", "pipe", "pipe"],
      cwd: process.cwd(),
      shell: true,
    });

    let stdout = "";
    let hadError = false;

    proc.stdout.on("data", (data: Buffer) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data: Buffer) => {
      const text = data.toString();
      if (text.includes("WebSocket") || text.includes("Attempting reconnect")) {
        hadError = true;
      }
    });

    const timeout = setTimeout(() => {
      proc.kill("SIGTERM");
      resolve(null);
    }, 10000);

    proc.on("close", code => {
      clearTimeout(timeout);
      if (code === 0 && !hadError && stdout.trim()) {
        resolve(stdout.trim());
      } else {
        resolve(null);
      }
    });

    proc.on("error", () => {
      clearTimeout(timeout);
      resolve(null);
    });
  });
}

function getFromEnvFile(varName: string): string | null {
  const envPath = join(process.cwd(), ".env.local");

  if (!existsSync(envPath)) {
    return null;
  }

  const content = readFileSync(envPath, "utf-8");
  const lines = content.split("\n");

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("#") || !trimmed) continue;

    const eqIndex = trimmed.indexOf("=");
    if (eqIndex === -1) continue;

    const key = trimmed.slice(0, eqIndex);
    let value = trimmed.slice(eqIndex + 1);

    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    if (key === varName) {
      return value;
    }
  }

  return null;
}

async function main() {
  console.log(`Getting ${envVarName}...`);

  const convexValue = await getFromConvex(envVarName);

  if (convexValue) {
    console.log(convexValue);
    return;
  }

  console.log("Convex CLI failed or timed out, trying .env.local fallback...");

  const fileValue = getFromEnvFile(envVarName);

  if (fileValue) {
    console.log(fileValue);
  } else {
    console.error(`Could not find ${envVarName} in Convex or .env.local`);
    process.exit(1);
  }
}

main().catch(console.error);

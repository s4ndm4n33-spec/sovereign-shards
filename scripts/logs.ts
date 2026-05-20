import { spawn } from "node:child_process";

const TIMEOUT_MS = 5000;
const MAX_LINES = parseInt(process.argv[2] || "50", 10);

const proc = spawn(
  "npx",
  ["convex", "logs", "--history", String(MAX_LINES), "--success"],
  {
    stdio: ["ignore", "pipe", "pipe"],
    cwd: process.cwd(),
    shell: true,
  },
);

let lineCount = 0;

proc.stdout.on("data", (data: Buffer) => {
  const text = data.toString();
  const lines = text.split("\n");
  for (const line of lines) {
    if (line.trim()) {
      console.log(line);
      if (!line.startsWith("Watching logs")) {
        lineCount++;
      }
    }
  }
});

proc.stderr.on("data", (data: Buffer) => {
  const text = data.toString();
  if (!text.includes("WebSocket") && !text.includes("Attempting reconnect")) {
    process.stderr.write(data);
  }
});

setTimeout(() => {
  proc.kill("SIGTERM");
  if (lineCount === 0) {
    console.log("(No recent log entries)");
  }
  process.exit(0);
}, TIMEOUT_MS);

proc.on("error", err => {
  console.error("Failed to start convex logs:", err.message);
  process.exit(1);
});

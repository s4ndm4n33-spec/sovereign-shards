import type { ProcessResult } from "./types";

const BASE = "/api";

export async function processFiles(
  files: File[],
  onProgress?: (pct: number, label: string) => void
): Promise<ProcessResult> {
  const formData = new FormData();
  for (const f of files) {
    formData.append("files", f);
  }

  onProgress?.(5, "Uploading archive…");
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `${BASE}/process`);
  xhr.responseType = "json";

  await new Promise<void>((resolve, reject) => {
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.min(45, 5 + Math.round((e.loaded / e.total) * 40));
        onProgress?.(pct, "Uploading archive…");
      }
    };
    xhr.upload.onload = () => onProgress?.(55, "Parsing conversations…");
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(xhr.response?.error || `HTTP ${xhr.status}`)));
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(formData);
  });

  const data = xhr.response as ProcessResult | { error: string };
  if (data && typeof data === "object" && "error" in data) {
    throw new Error(data.error);
  }
  onProgress?.(100, "Done");
  return data as ProcessResult;
}

export async function downloadPdf(result: ProcessResult, title: string) {
  const resp = await fetch(`${BASE}/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title,
      sessions: result.sessions,
      providers: result.providers,
      exec_summary: result.exec_summary,
      themes: result.themes,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error || "PDF generation failed");
  }
  const blob = await resp.blob();
  triggerDownload(blob, "VIC-report.pdf");
}

export async function downloadJsonl(result: ProcessResult) {
  const resp = await fetch(`${BASE}/jsonl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonl: result.jsonl }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error || "JSONL download failed");
  }
  const blob = await resp.blob();
  triggerDownload(blob, "archive.jsonl");
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

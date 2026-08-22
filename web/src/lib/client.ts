import type { Progress } from "@/app/api/redact/route";
import type { RedactedFile } from "./types";

export type Stage = "queued" | "reading" | "model" | "redacting" | "done" | "error";

export type Job = {
  id: string;
  name: string;
  size: number;
  stage: Stage;
  detail?: string;
  result?: RedactedFile;
  error?: string;
};

/** Reads the NDJSON progress stream and reports each stage as it lands. */
export async function redactFile(
  file: File,
  onProgress: (event: Progress) => void,
): Promise<void> {
  const body = new FormData();
  body.append("file", file);

  const response = await fetch("/api/redact", { method: "POST", body });
  if (!response.body) {
    onProgress({ stage: "error", error: "The server closed the connection." });
    return;
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;

    let newline = buffer.indexOf("\n");
    while (newline !== -1) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) onProgress(JSON.parse(line) as Progress);
      newline = buffer.indexOf("\n");
    }
  }
}

export function download(base64: string, mime: string, name: string) {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

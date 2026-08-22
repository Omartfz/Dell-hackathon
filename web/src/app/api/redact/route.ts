import {
  documentToText,
  extensionOf,
  parseDocument,
  rowsToCsv,
  sheetsToWorkbook,
} from "@/lib/documents";
import { modelName, proposeSpec } from "@/lib/ollama";
import { Redactor } from "@/lib/redact";
import type { RedactedFile } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 300;

const MAX_BYTES = 12 * 1024 * 1024;

/** Stages the client renders as chips. Each one is sent when it truly starts. */
export type Progress =
  | { stage: "reading" }
  | { stage: "model"; model: string }
  | { stage: "redacting"; proposed: number }
  | { stage: "done"; file: RedactedFile }
  | { stage: "error"; error: string };

function withSuffix(name: string, ext?: string): string {
  const dot = name.lastIndexOf(".");
  const stem = dot > 0 ? name.slice(0, dot) : name;
  const original = dot > 0 ? name.slice(dot + 1) : "txt";
  return `${stem}.safe.${ext ?? original}`;
}

async function run(file: File, send: (event: Progress) => void) {
  send({ stage: "reading" });
  const parsed = await parseDocument(file.name, Buffer.from(await file.arrayBuffer()));

  send({ stage: "model", model: modelName });
  const spec = await proposeSpec(documentToText(parsed));

  send({ stage: "redacting", proposed: spec.length });
  const redactor = new Redactor(spec);
  const ext = extensionOf(file.name);

  if (parsed.kind === "sheet") {
    const sheets = parsed.sheets.map((sheet) => ({
      name: sheet.name,
      rows: sheet.rows.map((row) => row.map((cell) => redactor.redact(cell))),
    }));

    const isDelimited = ext === "csv" || ext === "tsv";
    const download = isDelimited
      ? {
          base64: Buffer.from(
            rowsToCsv(sheets[0]?.rows ?? [], ext === "tsv" ? "\t" : ","),
            "utf8",
          ).toString("base64"),
          mime: "text/csv",
        }
      : {
          base64: sheetsToWorkbook(sheets).toString("base64"),
          mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        };

    send({
      stage: "done",
      file: {
        name: file.name,
        safeName: withSuffix(file.name),
        kind: "sheet",
        rows: sheets[0]?.rows ?? [],
        download,
        note:
          sheets.length > 1
            ? `${sheets.length} sheets were redacted, the preview shows the first.`
            : undefined,
        decisions: redactor.getDecisions(),
        metrics: redactor.getMetrics(),
      },
    });
    return;
  }

  const text = redactor.redact(parsed.text);
  const rebuilt = ext === "pdf" || ext === "docx";

  send({
    stage: "done",
    file: {
      name: file.name,
      safeName: withSuffix(file.name, rebuilt ? "txt" : undefined),
      kind: "text",
      text,
      download: {
        base64: Buffer.from(text, "utf8").toString("base64"),
        mime: "text/plain",
      },
      note: rebuilt
        ? "The text was redacted, the original layout was not rebuilt, so this downloads as .txt."
        : undefined,
      decisions: redactor.getDecisions(),
      metrics: redactor.getMetrics(),
    },
  });
}

export async function POST(request: Request) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: Progress) =>
        controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));

      try {
        const form = await request.formData();
        const file = form.get("file");

        if (!(file instanceof File)) {
          send({ stage: "error", error: "No file in the request." });
        } else if (file.size > MAX_BYTES) {
          send({
            stage: "error",
            error: `${file.name} is over 12 MB. Split it and try again.`,
          });
        } else {
          await run(file, send);
        }
      } catch (error) {
        const named = error as { name?: string; message?: string };
        const known =
          named?.name === "OllamaUnavailableError" ||
          named?.name === "UnsupportedFileError";
        if (!known) console.error("redact failed", error);
        send({
          stage: "error",
          error: known
            ? (named.message as string)
            : "Could not read that file. It may be encrypted, corrupt, or not what its extension claims.",
        });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "application/x-ndjson; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

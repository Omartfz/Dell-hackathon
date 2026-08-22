import * as XLSX from "xlsx";

export type ParsedDocument =
  | { kind: "sheet"; sheets: Array<{ name: string; rows: string[][] }> }
  | { kind: "text"; text: string };

export class UnsupportedFileError extends Error {
  constructor(ext: string) {
    super(`Cannot read a ${ext || "file"} yet. Try csv, xlsx, pdf, docx, json, txt or md.`);
    this.name = "UnsupportedFileError";
  }
}

export const SHEET_EXTS = ["xlsx", "xlsm", "xls", "csv", "tsv"];
export const TEXT_EXTS = ["txt", "md", "json", "log"];
export const DOC_EXTS = ["pdf", "docx"];

export function extensionOf(name: string): string {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

function sheetsFrom(buffer: Buffer): ParsedDocument {
  const book = XLSX.read(buffer, { type: "buffer", cellDates: true });
  const sheets = book.SheetNames.map((name) => {
    const rows = XLSX.utils.sheet_to_json<string[]>(book.Sheets[name], {
      header: 1,
      blankrows: false,
      defval: "",
      raw: false,
    });
    return { name, rows: rows.map((row) => row.map((cell) => String(cell ?? ""))) };
  });
  return { kind: "sheet", sheets };
}

async function pdfText(buffer: Buffer): Promise<string> {
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  const task = pdfjs.getDocument({
    data: new Uint8Array(buffer),
    useWorkerFetch: false,
    useSystemFonts: true,
  });

  try {
    const doc = await task.promise;
    const pages: string[] = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const content = await page.getTextContent();
      const line = content.items
        .map((item) => ("str" in item ? item.str : ""))
        .join(" ")
        .replace(/[ \t]+/g, " ")
        .trim();
      pages.push(line);
    }
    return pages.join("\n\n");
  } finally {
    await task.destroy();
  }
}

async function docxText(buffer: Buffer): Promise<string> {
  const mammoth = await import("mammoth");
  const { value } = await mammoth.extractRawText({ buffer });
  return value;
}

export async function parseDocument(
  name: string,
  buffer: Buffer,
): Promise<ParsedDocument> {
  const ext = extensionOf(name);

  if (SHEET_EXTS.includes(ext)) return sheetsFrom(buffer);
  if (TEXT_EXTS.includes(ext)) return { kind: "text", text: buffer.toString("utf8") };
  if (ext === "pdf") return { kind: "text", text: await pdfText(buffer) };
  if (ext === "docx") return { kind: "text", text: await docxText(buffer) };

  throw new UnsupportedFileError(ext);
}

/** Flattened view handed to the model. Sheets become tab separated lines. */
export function documentToText(doc: ParsedDocument): string {
  if (doc.kind === "text") return doc.text;
  return doc.sheets
    .map(
      (sheet) =>
        `# ${sheet.name}\n${sheet.rows.map((row) => row.join("\t")).join("\n")}`,
    )
    .join("\n\n");
}

export function sheetsToWorkbook(
  sheets: Array<{ name: string; rows: string[][] }>,
): Buffer {
  const book = XLSX.utils.book_new();
  for (const sheet of sheets) {
    XLSX.utils.book_append_sheet(
      book,
      XLSX.utils.aoa_to_sheet(sheet.rows),
      sheet.name.slice(0, 31),
    );
  }
  return XLSX.write(book, { type: "buffer", bookType: "xlsx" }) as Buffer;
}

export function rowsToCsv(rows: string[][], delimiter: string): string {
  return rows
    .map((row) =>
      row
        .map((cell) => {
          const needsQuotes =
            cell.includes(delimiter) || cell.includes('"') || cell.includes("\n");
          return needsQuotes ? `"${cell.replace(/"/g, '""')}"` : cell;
        })
        .join(delimiter),
    )
    .join("\n");
}

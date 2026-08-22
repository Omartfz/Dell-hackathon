export const KINDS = [
  "person",
  "organization",
  "email",
  "phone",
  "account",
  "card",
  "address",
  "id",
  "amount",
  "other",
] as const;

export type Kind = (typeof KINDS)[number];

export const OPS = ["alias", "band", "remove"] as const;

export type Op = (typeof OPS)[number];

/** What the local model proposes. It never gets to execute anything. */
export type SpecItem = {
  value: string;
  kind: Kind;
  op: Op;
};

export type Decision = {
  value: string;
  replacement: string;
  kind: Kind;
  op: Op;
  reason: string;
  source: "model" | "rule";
  count: number;
};

export type Metrics = {
  charsIn: number;
  charsOut: number;
  valuesFound: number;
  occurrences: number;
  aliased: number;
  banded: number;
  removed: number;
  caughtByRule: number;
};

export type FileKind = "sheet" | "text";

export type RedactedFile = {
  name: string;
  safeName: string;
  kind: FileKind;
  /** Preview rows for sheets. */
  rows?: string[][];
  /** Preview text for everything else. */
  text?: string;
  /** Base64 payload for the download, with its mime type. */
  download: { base64: string; mime: string };
  /** Set when the original format could not be rebuilt, e.g. pdf and docx. */
  note?: string;
  decisions: Decision[];
  metrics: Metrics;
};

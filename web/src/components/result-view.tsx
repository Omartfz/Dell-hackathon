"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/shell";
import { download } from "@/lib/client";
import type { Decision, RedactedFile } from "@/lib/types";

const OP_LABEL = {
  alias: "handle",
  band: "band",
  remove: "removed",
} as const;

const OP_TONE = {
  alias: "info",
  band: "warn",
  remove: "danger",
} as const;

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div>
      <p className="font-mono text-[22px] leading-none tracking-[-0.02em] text-ink">
        {value}
      </p>
      <p className="mono-micro mt-1.5">{label}</p>
    </div>
  );
}

function DecisionRow({ decision }: { decision: Decision }) {
  return (
    <li className="border-b border-line-2 py-3 last:border-0">
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 flex-1 truncate font-mono text-[12.5px] text-muted line-through">
          {decision.value}
        </p>
        <Chip tone={OP_TONE[decision.op]}>{OP_LABEL[decision.op]}</Chip>
      </div>
      <p className="mt-1 font-mono text-[12.5px] font-medium text-ink">
        {decision.replacement}
      </p>
      <p className="mt-1 text-[12.5px] text-faint">
        {decision.reason}
        {decision.source === "rule" ? " · hard rule" : ""}
        {decision.count > 1 ? ` · ${decision.count} times` : ""}
      </p>
    </li>
  );
}

export function ResultView({ file }: { file: RedactedFile }) {
  const { metrics, decisions } = file;
  const [header, ...body] = file.rows ?? [];

  return (
    <section className="rise glass rounded-[18px] p-6 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mono-eyebrow">03 · SAFE COPY</p>
          <h2 className="mt-2 truncate text-[22px] font-semibold tracking-[-0.03em]">
            {file.safeName}
          </h2>
          <p className="mt-1 text-[14px] text-muted">
            from {file.name}
            {file.note ? ` · ${file.note}` : ""}
          </p>
        </div>
        <Button
          onClick={() =>
            download(file.download.base64, file.download.mime, file.safeName)
          }
        >
          Download
        </Button>
      </div>

      <div className="mt-7 flex flex-wrap gap-x-12 gap-y-5 border-y border-line py-5">
        <Stat value={metrics.valuesFound} label="VALUES CHANGED" />
        <Stat value={metrics.occurrences} label="OCCURRENCES" />
        <Stat value={metrics.aliased} label="HANDLES" />
        <Stat value={metrics.banded} label="BANDED" />
        <Stat value={metrics.removed} label="REMOVED" />
        <Stat value={metrics.caughtByRule} label="CAUGHT BY RULE" />
      </div>

      <div className="mt-7 grid gap-7 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0">
          <p className="mono-eyebrow mb-3">WHAT YOU CAN SHARE</p>
          {file.kind === "sheet" && header ? (
            <div className="overflow-hidden rounded-[12px] border border-line bg-white">
              <div className="max-h-[440px] overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {header.map((cell, i) => (
                        <TableHead key={i}>{cell}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {body.slice(0, 200).map((row, i) => (
                      <TableRow key={i}>
                        {header.map((_, j) => (
                          <TableCell key={j}>{row[j] ?? ""}</TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              {body.length > 200 && (
                <p className="mono-micro border-t border-line px-3 py-2">
                  SHOWING 200 OF {body.length} ROWS. THE DOWNLOAD HAS ALL OF THEM.
                </p>
              )}
            </div>
          ) : (
            <pre className="max-h-[440px] overflow-auto rounded-[12px] border border-line bg-white p-4 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-ink-2">
              {file.text}
            </pre>
          )}
        </div>

        <aside className="min-w-0">
          <p className="mono-eyebrow mb-1">WHAT WAS TAKEN OUT</p>
          {decisions.length === 0 ? (
            <p className="mt-3 text-[14px] text-muted">
              Nothing matched. The document was already safe to share, which is
              worth checking by eye before you trust it.
            </p>
          ) : (
            <ul className="max-h-[440px] overflow-auto">
              {decisions.map((d) => (
                <DecisionRow key={`${d.kind}:${d.value}`} decision={d} />
              ))}
            </ul>
          )}
        </aside>
      </div>
    </section>
  );
}

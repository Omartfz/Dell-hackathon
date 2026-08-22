"use client";

import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

const ACCEPT =
  ".csv,.tsv,.xlsx,.xlsm,.xls,.pdf,.docx,.json,.txt,.md,.log";

export function Dropzone({
  onFiles,
  compact = false,
}: {
  onFiles: (files: File[]) => void;
  compact?: boolean;
}) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function take(list: FileList | null) {
    const files = [...(list ?? [])];
    if (files.length) onFiles(files);
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        take(e.dataTransfer.files);
      }}
      onClick={() => input.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          input.current?.click();
        }
      }}
      role="button"
      tabIndex={0}
      aria-label="Drop documents to redact"
      className={cn(
        "glass grid cursor-pointer place-items-center rounded-[18px] border-2 border-dashed text-center transition-all outline-none",
        compact ? "px-6 py-8" : "px-8 py-20",
        over
          ? "border-accent bg-accent-tint/70 shadow-overlay"
          : "border-border-input hover:border-ink",
      )}
    >
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
      <p className="mono-eyebrow">01 · DROP</p>
      <p
        className={cn(
          "mt-3 font-semibold tracking-[-0.025em]",
          compact ? "text-[17px]" : "text-[24px]",
        )}
      >
        {over ? "Let go" : "Drop the documents here"}
      </p>
      {!compact && (
        <p className="mt-2 max-w-[46ch] text-[14px] text-muted">
          Or click to browse. They are read on this machine and never uploaded
          anywhere.
        </p>
      )}
      <p className="mono-micro mt-4">
        CSV · TSV · XLSX · PDF · DOCX · JSON · TXT · MD
      </p>
    </div>
  );
}

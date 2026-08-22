import Link from "next/link";

import { cn } from "@/lib/utils";

export function Ambient() {
  return (
    <div className="ambient" aria-hidden>
      <span className="orb-sky" />
      <span className="orb-blush" />
      <span className="orb-mist" />
    </div>
  );
}

export function LogoMark() {
  return (
    <span className="grid size-[22px] place-items-center rounded-full border-2 border-ink">
      <span className="block h-[2px] w-[9px] -rotate-45 rounded-full bg-ink" />
    </span>
  );
}

export function Header({
  tagline,
  action,
}: {
  tagline?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="mx-auto flex w-full max-w-[1240px] items-center gap-4 px-6 py-5 md:px-12">
      <Link href="/" className="flex items-center gap-2.5">
        <LogoMark />
        <span className="text-[17px] font-semibold tracking-[-0.02em]">
          SafeContext
        </span>
      </Link>
      {tagline ? (
        <span className="mono-micro hidden md:block">{tagline}</span>
      ) : null}
      <div className="ml-auto">{action}</div>
    </header>
  );
}

const chipTones = {
  queued: "bg-[#f3f3f3] text-muted",
  info: "bg-accent-tint text-accent",
  success: "bg-success-tint text-success-ink",
  warn: "bg-warn-tint text-warn",
  danger: "bg-danger-tint text-danger",
} as const;

export type ChipTone = keyof typeof chipTones;

export function Chip({
  tone = "queued",
  children,
  className,
}: {
  tone?: ChipTone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-[11px] py-[5px] text-xs font-semibold",
        chipTones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Dot({
  tone = "info",
  live = false,
}: {
  tone?: ChipTone;
  live?: boolean;
}) {
  return (
    <span
      className={cn(
        "dot",
        live && "dot-live",
        tone === "success" && "dot-success",
        tone === "warn" && "dot-warn",
        tone === "danger" && "dot-danger",
      )}
    />
  );
}

/** Fixed band table. Same idea as docs/prd/02-features.md: 847291 -> "$500k-$1M". */
const BANDS: Array<{ max: number; label: string }> = [
  { max: 1_000, label: "under $1k" },
  { max: 10_000, label: "$1k-$10k" },
  { max: 50_000, label: "$10k-$50k" },
  { max: 100_000, label: "$50k-$100k" },
  { max: 500_000, label: "$100k-$500k" },
  { max: 1_000_000, label: "$500k-$1M" },
  { max: 5_000_000, label: "$1M-$5M" },
  { max: 25_000_000, label: "$5M-$25M" },
  { max: Infinity, label: "over $25M" },
];

export function bandFor(amount: number): string {
  const magnitude = Math.abs(amount);
  const band = BANDS.find((b) => magnitude < b.max) ?? BANDS[BANDS.length - 1];
  return amount < 0 ? `negative, ${band.label}` : band.label;
}

/**
 * Pulls a number out of the way people actually write money: "$847,291.00",
 * "EUR 1 200,50", "1.200,50 EUR". Returns null when it is not parseable, and
 * the caller then leaves the text alone rather than guessing.
 */
export function parseAmount(raw: string): number | null {
  const digits = raw.replace(/[^\d.,-]/g, "").trim();
  if (!digits) return null;

  const lastComma = digits.lastIndexOf(",");
  const lastDot = digits.lastIndexOf(".");
  const sep = lastComma > lastDot ? "," : lastDot > -1 ? "." : null;

  let normalized = digits;
  if (sep) {
    // A separator is decimal only when one or two digits follow it. Anything
    // else is thousands grouping, so "847,291" is not 847.291.
    const trailing = digits.length - digits.lastIndexOf(sep) - 1;
    normalized =
      trailing === 1 || trailing === 2
        ? digits.replace(sep === "," ? /\./g : /,/g, "").replace(sep, ".")
        : digits.replace(/[.,]/g, "");
  }

  const value = Number(normalized);
  return Number.isFinite(value) ? value : null;
}

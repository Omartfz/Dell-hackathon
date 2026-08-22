import { bandFor, parseAmount } from "./bands";
import type { Decision, Kind, Metrics, Op, SpecItem } from "./types";

const PREFIX: Record<Kind, string> = {
  person: "PERSON",
  organization: "ORG",
  email: "EMAIL",
  phone: "PHONE",
  account: "ACCT",
  card: "CARD",
  address: "ADDR",
  id: "ID",
  amount: "AMOUNT",
  other: "VALUE",
};

const ISO_DATE = /\d{4}-\d{2}-\d{2}/;

function digitCount(value: string): number {
  return (value.match(/\d/g) ?? []).length;
}

/**
 * Patterns that leave the document no matter what the model said. A planner
 * that misses an IBAN, or is talked into keeping one by something written
 * inside the file, must not be able to leak it.
 *
 * `accept` is what keeps the greedy patterns honest: dates and quantities are
 * usually the point of the report, so they must survive.
 */
type HardRule = {
  kind: Kind;
  op: Op;
  re: RegExp;
  reason: string;
  accept?: (match: string) => boolean;
};

const HARD_RULES: HardRule[] = [
  {
    kind: "email",
    op: "alias",
    re: /[\w.+-]+@[\w-]+\.[\w.-]+/g,
    reason: "Email address, always replaced",
  },
  {
    kind: "account",
    op: "alias",
    re: /\b[A-Z]{2}\d{2} ?(?:[A-Z0-9]{4} ?){2,7}[A-Z0-9]{1,4}\b/g,
    reason: "IBAN, always replaced",
  },
  {
    kind: "card",
    op: "alias",
    re: /\b(?:\d[ -]?){13,19}\b/g,
    reason: "Card number, always replaced",
    accept: luhnValid,
  },
  {
    kind: "phone",
    op: "alias",
    re: /(?:\+\d{1,3}[ .-]?)?(?:\(\d{2,4}\)[ .-]?)?\d{2,4}(?:[ .-]\d{2,4}){2,4}\b/g,
    reason: "Phone number, always replaced",
    accept: (m) => digitCount(m) >= 9 && !ISO_DATE.test(m),
  },
  {
    kind: "account",
    op: "alias",
    re: /\b\d{9,}\b/g,
    reason: "Long digit run, treated as an account number",
  },
  {
    kind: "amount",
    op: "band",
    re: /(?:[$€£]\s?\d[\d.,]*\d|[$€£]\s?\d|\b(?:USD|EUR|GBP|CAD|CHF) ?\d[\d.,]*|\b\d[\d.,]* ?(?:USD|EUR|GBP|CAD|CHF)\b)/g,
    reason: "Money, reduced to a band",
    accept: (m) => parseAmount(m) !== null,
  },
];

const OP_REASON: Record<Op, string> = {
  alias: "Identifier replaced with a stable handle",
  band: "Exact figure reduced to a band",
  remove: "Removed, not needed for the task",
};

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Card numbers only count if they pass Luhn, otherwise every long id matches. */
function luhnValid(digits: string): boolean {
  const clean = digits.replace(/\D/g, "");
  if (clean.length < 13 || clean.length > 19) return false;
  let sum = 0;
  let double = false;
  for (let i = clean.length - 1; i >= 0; i--) {
    let digit = clean.charCodeAt(i) - 48;
    if (double) {
      digit *= 2;
      if (digit > 9) digit -= 9;
    }
    sum += digit;
    double = !double;
  }
  return sum % 10 === 0;
}

/**
 * Executes a spec and then enforces the hard rules. One instance per document
 * so an alias means the same thing in every cell and on every page.
 */
export class Redactor {
  private aliases = new Map<string, string>();
  private counters = new Map<Kind, number>();
  private decisions = new Map<string, Decision>();
  private charsIn = 0;
  private charsOut = 0;

  constructor(private spec: SpecItem[] = []) {
    // Longest first, so "Jane Doe" is consumed before a bare "Jane".
    this.spec = [...spec].sort((a, b) => b.value.length - a.value.length);
  }

  private aliasFor(value: string, kind: Kind): string {
    const key = `${kind}:${value.toLowerCase()}`;
    const existing = this.aliases.get(key);
    if (existing) return existing;

    const next = (this.counters.get(kind) ?? 0) + 1;
    this.counters.set(kind, next);
    const alias = `${PREFIX[kind]}_${String(next).padStart(2, "0")}`;
    this.aliases.set(key, alias);
    return alias;
  }

  private replacementFor(value: string, kind: Kind, op: Op): string | null {
    if (op === "remove") return "[removed]";
    if (op === "band") {
      const amount = parseAmount(value);
      // Unparseable money is aliased rather than left in place.
      return amount === null ? this.aliasFor(value, kind) : bandFor(amount);
    }
    return this.aliasFor(value, kind);
  }

  private record(
    value: string,
    replacement: string,
    kind: Kind,
    op: Op,
    reason: string,
    source: "model" | "rule",
    count: number,
  ) {
    const key = `${kind}:${op}:${value}`;
    const existing = this.decisions.get(key);
    if (existing) {
      existing.count += count;
      return;
    }
    this.decisions.set(key, {
      value,
      replacement,
      kind,
      op,
      reason,
      source,
      count,
    });
  }

  /** Redacts one string: a cell, a paragraph, a whole page. */
  redact(input: string): string {
    if (!input) return input;
    this.charsIn += input.length;
    let out = input;

    for (const item of this.spec) {
      if (!item.value || item.value.length < 2) continue;
      const re = new RegExp(escapeRegExp(item.value), "gi");
      const matches = out.match(re);
      if (!matches) continue;

      const replacement = this.replacementFor(item.value, item.kind, item.op);
      if (replacement === null) continue;
      out = out.replace(re, replacement);
      this.record(
        item.value,
        replacement,
        item.kind,
        item.op,
        OP_REASON[item.op],
        "model",
        matches.length,
      );
    }

    for (const rule of HARD_RULES) {
      out = out.replace(new RegExp(rule.re.source, rule.re.flags), (match) => {
        const trimmed = match.trim();
        if (trimmed.length < 4) return match;
        if (rule.accept && !rule.accept(trimmed)) return match;

        const replacement = this.replacementFor(trimmed, rule.kind, rule.op);
        if (replacement === null) return match;
        this.record(
          trimmed,
          replacement,
          rule.kind,
          rule.op,
          rule.reason,
          "rule",
          1,
        );
        return match.replace(trimmed, replacement);
      });
    }

    this.charsOut += out.length;
    return out;
  }

  getDecisions(): Decision[] {
    return [...this.decisions.values()].sort((a, b) => b.count - a.count);
  }

  getMetrics(): Metrics {
    const decisions = this.getDecisions();
    return {
      charsIn: this.charsIn,
      charsOut: this.charsOut,
      valuesFound: decisions.length,
      occurrences: decisions.reduce((sum, d) => sum + d.count, 0),
      aliased: decisions.filter((d) => d.op === "alias").length,
      banded: decisions.filter((d) => d.op === "band").length,
      removed: decisions.filter((d) => d.op === "remove").length,
      caughtByRule: decisions.filter((d) => d.source === "rule").length,
    };
  }
}

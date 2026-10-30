import { ipoPhase, ipoSnapshots, ipoSubscriptions, ipos, rhpSource, subCategory } from "@/db/schema";
import { checkEnum, maybeDate, maybeDecimal, maybeInt, maybeString } from "./validate";

// Maps `data/snapshots/<time>.json` to rows for `ipos` (latest facts, merged),
// `ipo_snapshots` (insert-only, keyed by (ipo_key, taken_at)) and
// `ipo_subscriptions` (insert-only, keyed by (ipo_key, taken_at, category)) —
// docs/db.md § Where the data comes from. The snapshot's own `generated_at` is
// taken verbatim as `taken_at` and becomes `ipos.updated_at`; the routine-only
// fields (`needs_analysis`, `card_file`, `trend`, the inline `card`, …) are
// never imported. Rows use the tables' real insert types: timestamps are
// `Date`s (see types.ts), numerics `string`, integers and bigints `number`.

export type NewIpo = typeof ipos.$inferInsert;
export type NewSnapshot = typeof ipoSnapshots.$inferInsert;
export type NewSubscription = typeof ipoSubscriptions.$inferInsert;

export interface SnapshotRows {
  ipos: NewIpo[];
  snapshots: NewSnapshot[];
  subscriptions: NewSubscription[];
}

interface IpoEntry {
  key?: unknown;
  name?: unknown;
  open?: unknown;
  close?: unknown;
  allotment?: unknown;
  listing?: unknown;
  price?: unknown;
  lot?: unknown;
  size_cr?: unknown;
  gmp?: unknown;
  gmp_pct?: unknown;
  gmp_low?: unknown;
  gmp_high?: unknown;
  pe?: unknown;
  gmp_updated?: unknown;
  url?: unknown;
  rhp_url?: unknown;
  rhp_source?: unknown;
  phase?: unknown;
  anchor_done?: unknown;
  categories?: unknown;
  subscription?: Record<string, { shares_offered?: unknown; shares_bid?: unknown; times?: unknown }>;
  nse?: {
    symbol?: unknown;
    price_low?: unknown;
    issue_size_text?: unknown;
    face_value?: unknown;
    lead_managers?: unknown;
    registrar?: unknown;
  } | null;
}

export function parseSnapshotDocument(json: unknown, sourceFile: string): SnapshotRows {
  if (typeof json !== "object" || json === null) {
    throw new Error(`${sourceFile}: not a JSON object`);
  }
  const doc = json as { generated_at?: unknown; ipos?: unknown };
  const takenAt = maybeDate(doc.generated_at, `${sourceFile} generated_at`);
  if (takenAt === undefined) throw new Error(`${sourceFile}: missing generated_at`);
  if (!Array.isArray(doc.ipos)) throw new Error(`${sourceFile}: missing ipos array`);

  const rows: SnapshotRows = { ipos: [], snapshots: [], subscriptions: [] };
  for (const entry of doc.ipos as IpoEntry[]) {
    if (typeof entry !== "object" || entry === null) {
      throw new Error(`${sourceFile}: an ipos entry is not an object`);
    }
    const key = maybeString(entry.key);
    if (key === undefined) throw new Error(`${sourceFile}: an ipos entry is missing its key`);

    // `phase` is required by both rows; checked once, here.
    const phase = checkEnum(ipoPhase.enumValues, entry.phase, `${key}.phase`);
    if (phase === null) throw new Error(`${key}: missing phase`);

    // `ipos` facts — only fields present and non-null, so a later snapshot that
    // lacks NSE data cannot blank previously imported facts (docs/db.md
    // § `ipos`: "present" means key present and non-null), and `updated_at` is
    // the updating snapshot's `generated_at`, never now(). `Partial` because the
    // file decides which optional columns to carry (a later snapshot may lack
    // NSE data); the cast at the end states the row is complete enough for the
    // insert.
    const ipo: Partial<NewIpo> = { key, updatedAt: takenAt };
    const nse = entry.nse ?? {};
    const set = <K extends keyof NewIpo>(column: K, value: NewIpo[K] | null | undefined) => {
      if (value !== null && value !== undefined) ipo[column] = value;
    };
    set("name", maybeString(entry.name));
    set("openDate", maybeString(entry.open));
    set("closeDate", maybeString(entry.close));
    set("allotmentDate", maybeString(entry.allotment));
    set("listingDate", maybeString(entry.listing));
    set("priceHigh", maybeDecimal(entry.price, `${key}.price`));
    set("priceLow", maybeDecimal(nse.price_low, `${key}.nse.price_low`));
    set("lotSize", maybeInt(entry.lot, `${key}.lot`));
    set("issueSizeCr", maybeDecimal(entry.size_cr, `${key}.size_cr`));
    set("issueSizeText", maybeString(nse.issue_size_text));
    set("faceValue", maybeString(nse.face_value));
    set("leadManagers", maybeString(nse.lead_managers));
    set("registrar", maybeString(nse.registrar));
    set("symbol", maybeString(nse.symbol));
    set("rhpUrl", maybeString(entry.rhp_url));
    set("rhpSource", checkEnum(rhpSource.enumValues, entry.rhp_source, `${key}.rhp_source`));
    set("investorgainUrl", maybeString(entry.url));
    set("phase", phase);
    set("anchorDone", typeof entry.anchor_done === "boolean" ? entry.anchor_done : undefined);
    rows.ipos.push(ipo as NewIpo);

    // The snapshot row itself.
    const snapshot: NewSnapshot = {
      ipoKey: key,
      takenAt,
      phase,
      sourceFile,
    };
    const snapset = <K extends keyof NewSnapshot>(column: K, value: NewSnapshot[K] | null | undefined) => {
      if (value !== null && value !== undefined) snapshot[column] = value;
    };
    snapset("gmp", maybeDecimal(entry.gmp, `${key}.gmp`));
    snapset("gmpPct", maybeDecimal(entry.gmp_pct, `${key}.gmp_pct`));
    snapset("gmpLow", maybeDecimal(entry.gmp_low, `${key}.gmp_low`));
    snapset("gmpHigh", maybeDecimal(entry.gmp_high, `${key}.gmp_high`));
    snapset("pe", maybeDecimal(entry.pe, `${key}.pe`));
    snapset("gmpUpdated", maybeString(entry.gmp_updated));
    snapset("allotment", entry.categories);
    rows.snapshots.push(snapshot);

    // One subscription row per category; unknown categories throw (an enum
    // gap like the pre-2026-10-30 `shareholder` category used to be).
    for (const [category, sub] of Object.entries(entry.subscription ?? {})) {
      if (sub === null || typeof sub !== "object") {
        throw new Error(`${key}.subscription.${category}: not an object`);
      }
      const categoryValue = checkEnum(subCategory.enumValues, category, `${key}.subscription category`);
      const row: NewSubscription = { ipoKey: key, takenAt, category: categoryValue };
      const subset = <K extends keyof NewSubscription>(column: K, value: NewSubscription[K] | null | undefined) => {
        if (value !== null && value !== undefined) row[column] = value;
      };
      subset("sharesOffered", maybeInt(sub.shares_offered, `${key}.subscription.${category}.shares_offered`));
      subset("sharesBid", maybeInt(sub.shares_bid, `${key}.subscription.${category}.shares_bid`));
      subset("times", maybeDecimal(sub.times, `${key}.subscription.${category}.times`));
      rows.subscriptions.push(row);
    }
  }
  return rows;
}
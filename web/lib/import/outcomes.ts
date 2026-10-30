import { anchorGrade, ipoOutcomes, verdict } from "@/db/schema";
import { checkEnum, maybeDate, maybeDecimal, maybeString } from "./validate";

// Maps `data/outcomes.json` (the listing-day scorecard) to `ipo_outcomes`
// rows, one per listed IPO, replaced on the natural key. Numbers come from the
// file verbatim; the import computes nothing — the track record is task 012.
// `gmp_eve_snapshot` and `recorded_at` are timestamptz columns, converted to
// `Date`s (see types.ts). docs/db.md § Where the data comes from.

export type NewOutcome = typeof ipoOutcomes.$inferInsert;

export function parseOutcomesDocument(json: unknown): NewOutcome[] {
  if (typeof json !== "object" || json === null || Array.isArray(json)) {
    throw new Error("data/outcomes.json: not a JSON object keyed by IPO");
  }
  const rows: NewOutcome[] = [];
  for (const [key, entry] of Object.entries(json as Record<string, Record<string, unknown>>)) {
    if (entry === null || typeof entry !== "object") {
      throw new Error(`data/outcomes.json: ${key} is not an object`);
    }
    const o = entry as Record<string, unknown>;
    const row: Partial<NewOutcome> = { ipoKey: key };
    const set = <K extends keyof NewOutcome>(column: K, value: NewOutcome[K] | null | undefined) => {
      if (value !== null && value !== undefined) row[column] = value;
    };

    set("symbol", maybeString(o.symbol));
    set("listingDate", maybeString(o.listing_date));
    set("issuePrice", maybeDecimal(o.issue_price, `${key}.issue_price`));
    set("listingPrice", maybeDecimal(o.listing_price, `${key}.listing_price`));
    set("dayClose", maybeDecimal(o.day_close, `${key}.day_close`));
    set("dayHigh", maybeDecimal(o.day_high, `${key}.day_high`));
    set("dayLow", maybeDecimal(o.day_low, `${key}.day_low`));
    set("listingGainPct", maybeDecimal(o.listing_gain_pct, `${key}.listing_gain_pct`));
    set("closeGainPct", maybeDecimal(o.close_gain_pct, `${key}.close_gain_pct`));
    set("gmpEve", maybeDecimal(o.gmp_eve, `${key}.gmp_eve`));
    set("gmpEvePct", maybeDecimal(o.gmp_eve_pct, `${key}.gmp_eve_pct`));
    set("gmpEveSnapshot", maybeDate(o.gmp_eve_snapshot, `${key}.gmp_eve_snapshot`));
    set("gmpMissPts", maybeDecimal(o.gmp_miss_pts, `${key}.gmp_miss_pts`));
    set("verdict", checkEnum(verdict.enumValues, o.verdict, `${key} verdict`));
    set("verdictText", maybeString(o.verdict_text));
    set("bestCategory", maybeString(o.best_category));
    set("verdictReport", maybeString(o.verdict_report));
    set("anchorGrade", checkEnum(anchorGrade.enumValues, o.anchor_grade, `${key}.anchor_grade`));
    set("pe", maybeDecimal(o.pe, `${key}.pe`));
    set("sizeCr", maybeDecimal(o.size_cr, `${key}.size_cr`));
    set("subscriptionSource", maybeString(o.subscription_source));
    set("priceSource", maybeString(o.price_source));
    set("recordedAt", maybeDate(o.recorded_at, `${key}.recorded_at`));

    const subscription = o.subscription as Record<string, unknown> | null | undefined;
    set("subQib", maybeDecimal(subscription?.qib, `${key}.subscription.qib`));
    set("subSnii", maybeDecimal(subscription?.snii, `${key}.subscription.snii`));
    set("subBnii", maybeDecimal(subscription?.bnii, `${key}.subscription.bnii`));
    set("subRetail", maybeDecimal(subscription?.retail, `${key}.subscription.retail`));
    set("subTotal", maybeDecimal(subscription?.total, `${key}.subscription.total`));

    // A scored listing always carries symbol, listing_date, issue_price and
    // listing_price (the schema makes them NOT NULL); the file-driven build
    // above is partial by necessity — the cast states the row is complete for
    // the insert, which rejects an entry lacking them.
    rows.push(row as NewOutcome);
  }
  return rows;
}
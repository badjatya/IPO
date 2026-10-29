import { anchorGrade, ipoOutcomes, verdict } from "@/db/schema";
import { Loose } from "./types";
import { checkEnum, maybeNumber, maybeString } from "./validate";

// Maps `data/outcomes.json` (the listing-day scorecard) to `ipo_outcomes`
// rows, one per listed IPO, replaced on the natural key. Numbers come from the
// file verbatim; the import computes nothing — the track record is task 012.
// docs/db.md § Where the data comes from.

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
    const row: Loose<NewOutcome> = { ipoKey: key };
    const set = <K extends keyof NewOutcome>(column: K, value: Loose<NewOutcome>[K]) => {
      if (value !== null && value !== undefined) row[column] = value;
    };

    set("symbol", maybeString(o.symbol));
    set("listingDate", maybeString(o.listing_date));
    set("issuePrice", maybeNumber(o.issue_price, `${key}.issue_price`));
    set("listingPrice", maybeNumber(o.listing_price, `${key}.listing_price`));
    set("dayClose", maybeNumber(o.day_close, `${key}.day_close`));
    set("dayHigh", maybeNumber(o.day_high, `${key}.day_high`));
    set("dayLow", maybeNumber(o.day_low, `${key}.day_low`));
    set("listingGainPct", maybeNumber(o.listing_gain_pct, `${key}.listing_gain_pct`));
    set("closeGainPct", maybeNumber(o.close_gain_pct, `${key}.close_gain_pct`));
    set("gmpEve", maybeNumber(o.gmp_eve, `${key}.gmp_eve`));
    set("gmpEvePct", maybeNumber(o.gmp_eve_pct, `${key}.gmp_eve_pct`));
    set("gmpEveSnapshot", maybeString(o.gmp_eve_snapshot));
    set("gmpMissPts", maybeNumber(o.gmp_miss_pts, `${key}.gmp_miss_pts`));
    set("verdict", checkEnum(verdict.enumValues, o.verdict, `${key} verdict`));
    set("verdictText", maybeString(o.verdict_text));
    set("bestCategory", maybeString(o.best_category));
    set("verdictReport", maybeString(o.verdict_report));
    set("anchorGrade", checkEnum(anchorGrade.enumValues, o.anchor_grade, `${key}.anchor_grade`));
    set("pe", maybeNumber(o.pe, `${key}.pe`));
    set("sizeCr", maybeNumber(o.size_cr, `${key}.size_cr`));
    set("subscriptionSource", maybeString(o.subscription_source));
    set("priceSource", maybeString(o.price_source));
    set("recordedAt", maybeString(o.recorded_at));

    const subscription = o.subscription as Record<string, unknown> | null | undefined;
    set("subQib", maybeNumber(subscription?.qib, `${key}.subscription.qib`));
    set("subSnii", maybeNumber(subscription?.snii, `${key}.subscription.snii`));
    set("subBnii", maybeNumber(subscription?.bnii, `${key}.subscription.bnii`));
    set("subRetail", maybeNumber(subscription?.retail, `${key}.subscription.retail`));
    set("subTotal", maybeNumber(subscription?.total, `${key}.subscription.total`));

    rows.push(row as NewOutcome);
  }
  return rows;
}
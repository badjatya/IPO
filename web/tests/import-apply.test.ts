import { describe, expect, it } from "vitest";
import { PgDialect } from "drizzle-orm/pg-core";
import type { SQL } from "drizzle-orm";
import { ipoOutcomes, ipoVerdicts } from "@/db/schema";
import { commonReplacedSet } from "@/lib/import/apply";

// The batched "replaced on its natural key" SET (round-3 fix 12): whole
// reports' verdicts and the whole of data/outcomes.json now upsert in one
// statement per file, so the common SET must produce exactly what the per-row
// `replacedSet` it replaces produced, evaluated per conflicting row. These
// offline tests pin down the shape without a database; the db suite (tests a,
// d, h, i) verifies the end-to-end equivalence on a real branch.

const dialect = new PgDialect();
const render = (value: unknown) => dialect.sqlToQuery(value as SQL).sql;

describe("commonReplacedSet", () => {
  it("upserts a report's verdicts in one SET: carried columns reference excluded, absent nullable columns null out", () => {
    const set = commonReplacedSet(
      ipoVerdicts,
      [
        { reportDate: "2026-10-29", session: "PM", ipoKey: "a", verdict: "neutral", verdictText: "N", overrides: { summary: "x" } },
        { reportDate: "2026-10-29", session: "PM", ipoKey: "b" },
      ],
      ["reportDate", "session", "ipoKey"],
    );

    // Every non-key column of ipo_verdicts is nullable and appears in the SET.
    expect(Object.keys(set).toSorted()).toEqual([
      "bestCategory",
      "categoryNote",
      "overrides",
      "verdict",
      "verdictText",
    ]);
    // Carried by some rows → a plain excluded reference: a conflicting row
    // that carries the column gets its own value, one that does not gets null
    // (a nullable column's VALUES `default` is null) — per-row replacedSet's
    // exact behaviour for both.
    expect(render(set.verdict)).toBe("excluded.verdict");
    expect(render(set.verdictText)).toBe("excluded.verdict_text");
    expect(render(set.overrides)).toBe("excluded.overrides");
    // Carried by no row → the constant null update replacedSet would emit.
    expect(set.bestCategory).toBeNull();
    expect(set.categoryNote).toBeNull();
  });

  it("keeps a NOT NULL column a row lacks at its old value via coalesce", () => {
    // ipo_outcomes.recorded_at is NOT NULL with a default and the parser only
    // carries it when the file provides it, so a data/outcomes.json whose
    // entries disagree on recorded_at must hit the coalesce branch: the row
    // that carries it updates, the one that lacks it keeps the old value
    // (per-row replacedSet skipped NOT NULL columns the row lacked).
    const set = commonReplacedSet(
      ipoOutcomes,
      [
        { ipoKey: "a", symbol: "A", listingDate: "2026-11-04", issuePrice: "100", listingPrice: "110", recordedAt: new Date("2026-10-29T09:07+05:30") },
        { ipoKey: "b", symbol: "B", listingDate: "2026-11-04", issuePrice: "200", listingPrice: "210" },
      ],
      ["ipoKey"],
    );
    expect(render(set.recordedAt)).toBe('coalesce(excluded.recorded_at, "ipo_outcomes"."recorded_at")');
    // Carried by every row (the NOT NULL facts) → a plain excluded reference.
    expect(render(set.symbol)).toBe("excluded.symbol");
    expect(render(set.issuePrice)).toBe("excluded.issue_price");
    // Carried by no row → null update (nullable) / skipped (NOT NULL).
    expect(set.dayClose).toBeNull();
    expect(set.anchorGrade).toBeNull();
  });

  it("skips a NOT NULL column no row carries", () => {
    const set = commonReplacedSet(
      ipoOutcomes,
      [
        { ipoKey: "a", symbol: "A", listingDate: "2026-11-04", issuePrice: "1", listingPrice: "2" },
        { ipoKey: "b", symbol: "B", listingDate: "2026-11-04", issuePrice: "3", listingPrice: "4" },
      ],
      ["ipoKey"],
    );
    expect("recordedAt" in set).toBe(false); // NOT NULL, absent from every row
    expect(set.dayClose).toBeNull(); // nullable, absent from every row
  });
});
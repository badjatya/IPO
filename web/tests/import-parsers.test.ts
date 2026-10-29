import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseAnalysisDocument } from "@/lib/import/analysis";
import { parseCardDocument } from "@/lib/import/card";
import { repoRoot } from "@/lib/import/git";
import { parseOutcomesDocument } from "@/lib/import/outcomes";
import { parseReportDocument } from "@/lib/import/report";
import { parseSnapshotDocument } from "@/lib/import/snapshot";

// The parsers against the repo's own committed files (docs/db.md § Where the
// data comes from), plus tiny synthetic fixtures for properties no committed
// file carries yet: provenance fields on cards and reports (task 004's fields
// are optional, so until the routine writes them nothing committed has them)
// and a `"generated": "quiet"` report shaped like ipo_agent/quiet.py's output.

const root = repoRoot(process.cwd());
const read = (path: string) => readFileSync(join(root, path), "utf8");
const json = (path: string) => JSON.parse(read(path)) as Record<string, never>;

const findIpo = (rows: ReturnType<typeof parseSnapshotDocument>, key: string) => {
  const ipo = rows.ipos.find((row) => row.key === key);
  expect(ipo, `expected an ipos row for ${key}`).toBeDefined();
  return ipo!;
};
const findSnapshot = (rows: ReturnType<typeof parseSnapshotDocument>, key: string) => {
  const snapshot = rows.snapshots.find((row) => row.ipoKey === key);
  expect(snapshot, `expected a snapshot row for ${key}`).toBeDefined();
  return snapshot!;
};
const findSubscription = (rows: ReturnType<typeof parseSnapshotDocument>, key: string, category: string) => {
  const row = rows.subscriptions.find((s) => s.ipoKey === key && s.category === category);
  expect(row, `expected a ${category} subscription row for ${key}`).toBeDefined();
  return row!;
};

describe("snapshot parser", () => {
  it("maps a real snapshot's entry to ipos / ipo_snapshots / ipo_subscriptions rows", () => {
    const rows = parseSnapshotDocument(json("data/snapshots/2026-10-29T0907.json"), "data/snapshots/2026-10-29T0907.json");

    const ipo = findIpo(rows, "sfc-environmental-technologies");
    expect(ipo.name).toBe("SFC Environmental Technologies");
    expect(ipo.priceHigh).toBe(330);
    expect(ipo.priceLow).toBe(313);
    expect(ipo.symbol).toBe("SFCTECH");
    expect(ipo.lotSize).toBe(45);
    expect(ipo.issueSizeCr).toBe(667.53);
    expect(ipo.rhpUrl).toContain("RHP_SFCTECH.zip");
    expect(ipo.rhpSource).toBe("nse");
    expect(ipo.investorgainUrl).toContain("investorgain.com");
    expect(ipo.anchorDone).toBe(true);
    expect(ipo.phase).toBe("closing_today");
    // updated_at is the snapshot's own generated_at, never now().
    expect(ipo.updatedAt).toBe("2026-10-29T09:07+05:30");

    const snapshot = findSnapshot(rows, "sfc-environmental-technologies");
    expect(snapshot.takenAt).toBe("2026-10-29T09:07+05:30");
    expect(snapshot.gmp).toBe(10);
    expect(snapshot.gmpPct).toBe(3.03);
    expect(snapshot.gmpUpdated).toBe("28-Oct 23:37");
    expect(snapshot.pe).toBe(19.24);
    expect(snapshot.sourceFile).toBe("data/snapshots/2026-10-29T0907.json");
    expect(Array.isArray(snapshot.allotment)).toBe(true);

    const retail = findSubscription(rows, "sfc-environmental-technologies", "retail");
    expect(retail.sharesOffered).toBe(7079872);
    expect(retail.sharesBid).toBe(1435005);
    expect(retail.times).toBe(0.2);
    expect(findSubscription(rows, "sfc-environmental-technologies", "total").times).toBe(0.15);
  });

  it("maps a shareholder subscription category to a row (the decided enum value)", () => {
    const rows = parseSnapshotDocument(json("data/snapshots/2026-10-23T1908.json"), "data/snapshots/2026-10-23T1908.json");
    const shareholder = findSubscription(rows, "jio-platforms", "shareholder");
    expect(shareholder.sharesOffered).toBe(22341376);
    expect(shareholder.sharesBid).toBe(120044304);
    expect(shareholder.times).toBe(5.37);
    expect(findSubscription(rows, "jio-platforms", "employee").times).toBe(1.87);
  });

  it("leaves fields a file lacks out of the row (they store as null)", () => {
    const rows = parseSnapshotDocument(
      {
        generated_at: "2026-10-15T09:07+05:30",
        ipos: [
          { key: "bare", name: "Bare", phase: "announced", gmp: null, subscription: null, categories: null },
          { key: "with-nse", name: "With NSE", phase: "open", nse: { symbol: "BNSE" } },
        ],
      } as never,
      "data/snapshots/2026-10-15T0907.json",
    );
    expect(rows.subscriptions).toEqual([]);
    const bare = findSnapshot(rows, "bare");
    expect(bare.gmp).toBeUndefined();
    expect(bare.allotment).toBeUndefined();
    expect(findIpo(rows, "bare")).not.toHaveProperty("symbol");
    expect(findIpo(rows, "with-nse").symbol).toBe("BNSE");
    expect(findIpo(rows, "with-nse")).not.toHaveProperty("priceLow");
  });

  it("throws on an unknown phase or subscription category", () => {
    expect(() =>
      parseSnapshotDocument(
        { generated_at: "2026-10-15T09:07+05:30", ipos: [{ key: "x", name: "X", phase: "banana" }] } as never,
        "data/snapshots/x.json",
      ),
    ).toThrow(/phase/);
    expect(() =>
      parseSnapshotDocument(
        {
          generated_at: "2026-10-15T09:07+05:30",
          ipos: [{ key: "x", name: "X", phase: "open", subscription: { foo: { times: 1 } } }],
        } as never,
        "data/snapshots/x.json",
      ),
    ).toThrow(/subscription category/);
  });

  it("throws on a non-object file", () => {
    expect(() => parseSnapshotDocument("[]", "data/snapshots/x.json")).toThrow(/not a JSON object/);
  });
});

describe("card parser", () => {
  it("maps a real card", () => {
    const card = parseCardDocument(json("analysis/zetwerk.json"), "zetwerk", "analysis/zetwerk.json");
    expect(card.ipoKey).toBe("zetwerk");
    expect(card.source).toBe("rhp");
    expect(card.analysedOn).toBe("2026-10-13");
    expect(card.verdict).toBe("neutral");
    expect(card.verdictText).toBe("Neutral");
    expect(card.summary).toContain("Tech-led");
    expect(card.positives).toHaveLength(2);
    expect(card.redFlags).toHaveLength(3);
    expect(card.anchor).toContain("₹2,251 Cr");
    expect(card.anchorGrade).toBe("strong");
    expect(card.sourceFile).toBe("analysis/zetwerk.json");
    // A legacy card carries no provenance: the row must not mention it.
    expect(card).not.toHaveProperty("aiModel");
    expect(card).not.toHaveProperty("aiPromptVersion");
    expect(card).not.toHaveProperty("aiWrittenAt");
  });

  it("copies provenance when the card carries it, and nulls it otherwise", () => {
    const withAi = parseCardDocument(
      {
        name: "X",
        source: "web",
        verdict: "apply",
        verdict_text: "Apply",
        anchor_grade: "pending",
        ai_model: "claude-sonnet-5-5",
        ai_prompt_version: "v1",
        ai_written_at: "2026-10-13T09:00+05:30",
      } as never,
      "x",
      "analysis/x.json",
    );
    expect(withAi.aiModel).toBe("claude-sonnet-5-5");
    expect(withAi.aiPromptVersion).toBe("v1");
    expect(withAi.aiWrittenAt).toBe("2026-10-13T09:00+05:30");

    const withoutAi = parseCardDocument(
      { name: "X", source: "web", verdict: "apply", verdict_text: "Apply", anchor_grade: "pending" } as never,
      "x",
      "analysis/x.json",
    );
    expect(withoutAi).not.toHaveProperty("aiModel");
    expect(withoutAi).not.toHaveProperty("aiWrittenAt");
  });

  it("throws on an unknown verdict", () => {
    expect(() =>
      parseCardDocument(
        { name: "X", source: "rhp", verdict: "buy", verdict_text: "Buy", anchor_grade: "strong" } as never,
        "x",
        "analysis/x.json",
      ),
    ).toThrow(/verdict/);
  });
});

describe("analysis parser", () => {
  it("hashes the markdown and names the RHP text path", () => {
    const markdown = read("analysis/zetwerk.md");
    const analysis = parseAnalysisDocument(markdown, "zetwerk");
    expect(analysis.ipoKey).toBe("zetwerk");
    expect(analysis.markdown).toBe(markdown);
    expect(analysis.rhpTextPath).toBe("analysis/rhp/zetwerk.txt");
    expect(analysis.contentSha).toMatch(/^[0-9a-f]{64}$/);
    expect(analysis.contentSha).toBe(createHash("sha256").update(markdown).digest("hex"));
    expect(analysis).not.toHaveProperty("aiModel");
  });
});

describe("report parser", () => {
  it("maps a real report, with extra card fields going to overrides", () => {
    const { report, verdicts } = parseReportDocument(json("reports/2026-10-13-am.json"), "reports/2026-10-13-am.json");
    expect(report.reportDate).toBe("2026-10-13");
    expect(report.session).toBe("AM");
    expect(report.quiet).toBe(false);
    expect(report.headline).toContain("HD Fire Protect");
    expect(report.notes).toHaveLength(2);
    expect(report.sourceFile).toBe("reports/2026-10-13-am.json");
    expect(report).not.toHaveProperty("carriedFrom");
    expect(report).not.toHaveProperty("aiModel");

    expect(verdicts).toHaveLength(7);
    const hd = verdicts.find((row) => row.ipoKey === "hd-fire-protect")!;
    expect(hd.verdict).toBe("apply");
    expect(hd.verdictText).toBe("Apply");
    expect(hd.bestCategory).toBe("Retail");
    // Every non-verdict field of the entry lands in overrides as a whole.
    expect(Object.keys(hd.overrides ?? {})).toEqual(
      expect.arrayContaining(["summary", "financials", "quota", "positives", "red_flags", "anchor", "anchor_grade"]),
    );

    const zetwerk = verdicts.find((row) => row.ipoKey === "zetwerk")!;
    expect(zetwerk.verdict).toBe("pending");
    expect(Object.keys(zetwerk.overrides ?? {})).toEqual(["summary", "red_flags"]);
    const fusion = verdicts.find((row) => row.ipoKey === "fusion-cx")!;
    expect(fusion).not.toHaveProperty("bestCategory"); // the file has best_category: null
  });

  it("parses every committed report and gives one verdict row per entry", () => {
    // Relative to the repo root: reports/<date>-<am|pm>.json (the list is
    // derived at run time from the index, never pinned).
    const list = execFileSync("git", ["ls-files", "reports/*.json"], { cwd: root, encoding: "utf8" })
      .trim()
      .split("\n")
      .filter(Boolean);
    expect(list.length).toBeGreaterThan(0);
    for (const path of list) {
      const { report, verdicts } = parseReportDocument(json(path), path);
      const doc = json(path) as { ipos?: Record<string, unknown> };
      expect(report.reportDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(verdicts).toHaveLength(Object.keys(doc.ipos ?? {}).length);
    }
  });

  it("maps an entry with no verdict to a null-verdict row (coalesce(verdict, card.verdict) in the app)", () => {
    // Real shape: reports/2026-10-19-am.json's tonbo-imaging entry carries only
    // best_category and category_note.
    const { verdicts } = parseReportDocument(
      {
        date: "2026-10-19",
        session: "AM",
        headline: "x",
        ipos: { "tonbo-imaging": { best_category: "Retail", category_note: "GMP rising" } },
      } as never,
      "reports/2026-10-19-am.json",
    );
    const tonbo = verdicts[0]!;
    expect(tonbo.verdict).toBeUndefined();
    expect(tonbo.bestCategory).toBe("Retail");
    expect(tonbo.overrides).toBeUndefined();
  });

  it("maps a quiet run like quiet.py writes it (generated: quiet, carried_from, no provenance)", () => {
    const { report, verdicts } = parseReportDocument(
      {
        date: "2026-10-30",
        session: "AM",
        headline: "No IPO open; carrying calls forward",
        ipos: { "jio-platforms": { verdict: "listing_gains", verdict_text: "Listing gains only" } },
        notes: ["Quiet run: no IPO open and nothing new to research. Numbers refreshed; calls carried over from the 2026-10-29 PM brief."],
        generated: "quiet",
        carried_from: "2026-10-29-pm.json",
      } as never,
      "reports/2026-10-30-am.json",
    );
    expect(report.quiet).toBe(true);
    expect(report.carriedFrom).toBe("2026-10-29-pm.json");
    expect(report).not.toHaveProperty("aiModel");
    expect(verdicts[0]!.verdict).toBe("listing_gains");
  });

  it("throws on an unknown verdict value", () => {
    expect(() =>
      parseReportDocument(
        { date: "2026-10-13", session: "AM", ipos: { "hd-fire-protect": { verdict: "maybe" } } } as never,
        "reports/2026-10-13-am.json",
      ),
    ).toThrow(/verdict/);
  });
});

describe("outcomes parser", () => {
  it("maps every scored listing, with subscription going to sub_* columns", () => {
    const rows = parseOutcomesDocument(json("data/outcomes.json"));
    expect(rows.length).toBeGreaterThan(0);
    const hd = rows.find((row) => row.ipoKey === "hd-fire-protect")!;
    expect(hd.symbol).toBe("HDFIRE");
    expect(hd.listingDate).toBe("2026-10-21");
    expect(hd.issuePrice).toBe(271);
    expect(hd.listingPrice).toBe(335);
    expect(hd.listingGainPct).toBe(23.62);
    expect(hd.gmpEveSnapshot).toBe("2026-10-20T19:09+05:30");
    expect(hd.verdict).toBe("apply");
    expect(hd.verdictReport).toBe("2026-10-15-am.json");
    expect(hd.subQib).toBe(156.82);
    expect(hd.subRetail).toBe(20.83);
    expect(hd.subTotal).toBe(82.41);

    const zetwerk = rows.find((row) => row.ipoKey === "zetwerk")!;
    expect(zetwerk.verdict).toBe("avoid");
    expect(zetwerk.anchorGrade).toBe("strong");
    expect(zetwerk.pe).toBe(-14.17);
    expect(zetwerk.sizeCr).toBe(5012.33);
  });
});
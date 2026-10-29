import { describe, expect, it } from "vitest";
import * as schema from "@/db/schema";

// Offline extra: the module must expose every table, enum and the view db.md
// lists. The real schema check against a migrated branch is tests/db/.
const tables = [
  "ipos",
  "ipoSnapshots",
  "ipoSubscriptions",
  "ipoCards",
  "ipoAnalyses",
  "reports",
  "ipoVerdicts",
  "ipoOutcomes",
  "stocks",
  "stockAnalyses",
  "stockQuotes",
  "quarterlyResults",
  "shareholding",
  "announcements",
  "alerts",
  "users",
  "session",
  "account",
  "verification",
  "rateLimit",
  "watchlistItems",
  "aiQuestions",
  "analysisJobs",
  "analysisJobEvents",
  "analysisRequests",
  "settings",
  "imports",
];

// The relations that let Better Auth's adapter join (task 010).
const relations = ["userRelations", "sessionRelations", "accountRelations"];

const enums = [
  "ipoPhase",
  "verdict",
  "anchorGrade",
  "cardSource",
  "rhpSource",
  "reportSession",
  "subCategory",
  "importance",
  "jobStatus",
  "analysisServed",
  "alertKind",
  "severity",
];

describe("db schema module", () => {
  // Cast away the namespace so the import rule's computed-access check doesn't fire.
  const exported = schema as unknown as Record<string, unknown>;

  it("exports all 27 tables from db.md", () => {
    for (const name of tables) {
      expect(exported[name]).toBeDefined();
    }
  });

  it("exports all 12 enums from db.md", () => {
    for (const name of enums) {
      expect(exported[name]).toBeDefined();
    }
  });

  it("exports the watched_symbols view", () => {
    expect(exported.watchedSymbols).toBeDefined();
  });

  it("exports the relations Better Auth's adapter joins on (task 010)", () => {
    for (const name of relations) {
      expect(exported[name]).toBeDefined();
    }
  });

  it("exports nothing unexpected", () => {
    const expected = new Set([...tables, ...relations, ...enums, "watchedSymbols"]);
    expect(Object.keys(exported).filter((name) => !expected.has(name))).toEqual([]);
  });
});
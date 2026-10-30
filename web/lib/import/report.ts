import { ipoVerdicts, reportSession, reports, verdict } from "@/db/schema";
import { checkEnum, maybeDate, maybeString } from "./validate";

// Maps `reports/<date>-<am|pm>.json` to one `reports` row and one
// `ipo_verdicts` row per entry (docs/db.md § Where the data comes from). Only
// the four call fields go to verdict columns; every other entry field goes into
// `overrides` as a whole, and verdicts without a `verdict` insert null (the app
// shows `coalesce(verdict, card.verdict)`). A `"generated": "quiet"` report
// (written by `ipo_agent/quiet.py`, not Claude) maps to `quiet = true` and
// keeps `carried_from`, with null provenance. `commit_sha` is filled by the
// apply layer — the imported commit per commit, `git log -1` on the path in a
// rebuild. `ai_written_at` is a timestamptz, converted to a `Date` (types.ts).

export type NewReport = typeof reports.$inferInsert;
export type NewVerdict = typeof ipoVerdicts.$inferInsert;

const VERDICT_FIELDS = ["verdict", "verdict_text", "best_category", "category_note"];

export interface ReportRows {
  report: NewReport;
  verdicts: NewVerdict[];
}

export function parseReportDocument(json: unknown, sourceFile: string): ReportRows {
  if (typeof json !== "object" || json === null) {
    throw new Error(`${sourceFile}: not a JSON object`);
  }
  const doc = json as Record<string, unknown>;

  const reportDate = maybeString(doc.date);
  if (reportDate === undefined) throw new Error(`${sourceFile}: missing date`);
  const session = checkEnum(reportSession.enumValues, doc.session, `${sourceFile} session`);
  if (session === null) throw new Error(`${sourceFile}: missing session`);

  const report: NewReport = {
    reportDate,
    session,
    quiet: doc.generated === "quiet",
    notes: Array.isArray(doc.notes) ? (doc.notes as string[]) : [],
    sourceFile,
  };
  const set = <K extends keyof NewReport>(column: K, value: NewReport[K] | null | undefined) => {
    if (value !== null && value !== undefined) report[column] = value;
  };
  set("headline", maybeString(doc.headline));
  set("carriedFrom", maybeString(doc.carried_from));
  set("aiModel", maybeString(doc.ai_model));
  set("aiPromptVersion", maybeString(doc.ai_prompt_version));
  set("aiWrittenAt", maybeDate(doc.ai_written_at, `${sourceFile} ai_written_at`));

  const verdicts: NewVerdict[] = [];
  for (const [ipoKey, entry] of Object.entries((doc.ipos ?? {}) as Record<string, Record<string, unknown>>)) {
    if (entry === null || typeof entry !== "object") {
      throw new Error(`${sourceFile}: ${ipoKey} is not an object`);
    }
    const row: NewVerdict = { reportDate, session, ipoKey };
    const setVerdict = <K extends keyof NewVerdict>(column: K, value: NewVerdict[K] | null | undefined) => {
      if (value !== null && value !== undefined) row[column] = value;
    };
    setVerdict("verdict", checkEnum(verdict.enumValues, entry.verdict, `${ipoKey} verdict`));
    setVerdict("verdictText", maybeString(entry.verdict_text));
    setVerdict("bestCategory", maybeString(entry.best_category));
    setVerdict("categoryNote", maybeString(entry.category_note));
    const overrides: Record<string, unknown> = {};
    for (const [field, value] of Object.entries(entry)) {
      if (!VERDICT_FIELDS.includes(field) && value !== null && value !== undefined) overrides[field] = value;
    }
    if (Object.keys(overrides).length > 0) row.overrides = overrides;
    verdicts.push(row);
  }

  return { report, verdicts };
}
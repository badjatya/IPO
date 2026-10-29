import { ipoVerdicts, reportSession, reports, verdict } from "@/db/schema";
import { Loose } from "./types";
import { checkEnum, maybeString } from "./validate";

// Maps `reports/<date>-<am|pm>.json` to one `reports` row and one
// `ipo_verdicts` row per entry (docs/db.md § Where the data comes from). Only
// the four call fields go to verdict columns; every other entry field goes into
// `overrides` as a whole, and verdicts without a `verdict` insert null (the app
// shows `coalesce(verdict, card.verdict)`). A `"generated": "quiet"` report
// (written by `ipo_agent/quiet.py`, not Claude) maps to `quiet = true` and
// keeps `carried_from`, with null provenance. `commit_sha` is filled by the
// apply layer — the imported commit per commit, `git log -1` on the path in a
// rebuild.

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

  const report: Loose<NewReport> = {
    reportDate,
    session,
    quiet: doc.generated === "quiet",
    notes: Array.isArray(doc.notes) ? (doc.notes as string[]) : [],
    sourceFile,
  };
  if (doc.headline !== null && doc.headline !== undefined) report.headline = String(doc.headline);
  if (doc.carried_from !== null && doc.carried_from !== undefined) {
    report.carriedFrom = String(doc.carried_from);
  }
  if (doc.ai_model !== null && doc.ai_model !== undefined) report.aiModel = String(doc.ai_model);
  if (doc.ai_prompt_version !== null && doc.ai_prompt_version !== undefined) {
    report.aiPromptVersion = String(doc.ai_prompt_version);
  }
  if (doc.ai_written_at !== null && doc.ai_written_at !== undefined) {
    report.aiWrittenAt = String(doc.ai_written_at);
  }

  const verdicts: NewVerdict[] = [];
  for (const [ipoKey, entry] of Object.entries((doc.ipos ?? {}) as Record<string, Record<string, unknown>>)) {
    if (entry === null || typeof entry !== "object") {
      throw new Error(`${sourceFile}: ${ipoKey} is not an object`);
    }
    const row: Loose<NewVerdict> = { reportDate, session, ipoKey };
    if (entry.verdict !== null && entry.verdict !== undefined) {
      row.verdict = checkEnum(verdict.enumValues, entry.verdict, `${ipoKey} verdict`);
    }
    if (entry.verdict_text !== null && entry.verdict_text !== undefined) {
      row.verdictText = String(entry.verdict_text);
    }
    if (entry.best_category !== null && entry.best_category !== undefined) {
      row.bestCategory = String(entry.best_category);
    }
    if (entry.category_note !== null && entry.category_note !== undefined) {
      row.categoryNote = String(entry.category_note);
    }
    const overrides: Record<string, unknown> = {};
    for (const [field, value] of Object.entries(entry)) {
      if (!VERDICT_FIELDS.includes(field) && value !== null && value !== undefined) overrides[field] = value;
    }
    if (Object.keys(overrides).length > 0) row.overrides = overrides;
    verdicts.push(row as NewVerdict);
  }

  return { report: report as NewReport, verdicts };
}
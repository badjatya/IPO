import { eq, getTableColumns, sql } from "drizzle-orm";
import {
  ipoAnalyses,
  ipoCards,
  ipoOutcomes,
  ipoSnapshots,
  ipoSubscriptions,
  ipoVerdicts,
  ipos,
  reports,
} from "@/db/schema";
import { parseAnalysisDocument } from "./analysis";
import { parseCardDocument } from "./card";
import { classifyResearchFile, researchKey } from "./files";
import { changedPaths, headSha, lastCommitTouching, listResearchFilesAtHead, readFilesAt } from "./git";
import { recordFailed, recordOk } from "./log";
import { parseOutcomesDocument } from "./outcomes";
import { parseReportDocument } from "./report";
import { parseSnapshotDocument } from "./snapshot";
import type { ImportDb, ImportTx } from "./types";

// The apply layer: one transaction per commit (and one for the whole-repo
// rebuild), reading every file from the commit itself or from HEAD — never the
// working tree. Upserts run in foreign-key order: `ipos`, then snapshots +
// subscriptions (insert-only), then cards and analyses, then reports + verdicts,
// then outcomes; each transaction starts with an advisory xact lock so a local
// run and the Action (009) can't interleave. docs/db.md § Import and rebuild.

/** The fixed advisory-lock key serialising import and rebuild runs. */
export const ADVISORY_LOCK_KEY = 871200800;

export interface CommitOutcome {
  sha: string;
  files: number;
  ok: boolean;
  error?: string;
}

// ---------------------------------------------------------------------------
// Upsert helpers
// ---------------------------------------------------------------------------

/**
 * The update set for a row that is *replaced* on its natural key (cards,
 * analyses, reports, verdicts, outcomes): every column of the table the row
 * does not carry (and that may be null) becomes null, so a file edit that drops
 * a field converges the row to the file. NOT NULL columns the row lacks are
 * left alone; `keys` (the conflict target) never appear in the SET.
 */
function replacedSet(
  table: Parameters<typeof getTableColumns>[0],
  row: Record<string, unknown>,
  keys: string[],
): Record<string, unknown> {
  const set: Record<string, unknown> = {};
  for (const [column, meta] of Object.entries(getTableColumns(table))) {
    if (keys.includes(column)) continue;
    const value = row[column];
    if (value !== undefined) {
      set[column] = value;
    } else if (!meta.notNull) {
      set[column] = null;
    }
  }
  return set;
}

/**
 * `ipos` is merged, not replaced: only fields present and non-null in the
 * updating snapshot apply, so a later snapshot without NSE data cannot blank
 * previously imported facts (docs/db.md § `ipos`). The parser emits exactly the
 * present fields, so the SET is simply the row minus its key — and a snapshot
 * with no facts at all degrades to insert-only.
 */
async function upsertIpos(tx: ImportTx, rows: typeof ipos.$inferInsert[]): Promise<void> {
  for (const row of rows) {
    const set = { ...row };
    delete (set as { key?: string }).key;
    if (Object.keys(set).length === 0) {
      await tx.insert(ipos).values(row).onConflictDoNothing();
    } else {
      await tx.insert(ipos).values(row).onConflictDoUpdate({ target: ipos.key, set });
    }
  }
}

// ---------------------------------------------------------------------------
// One file
// ---------------------------------------------------------------------------

async function applyFile(tx: ImportTx, path: string, content: string, reportCommitSha: string | null): Promise<void> {
  const kind = classifyResearchFile(path);
  if (kind === null) return;

  switch (kind) {
    case "snapshot": {
      const rows = parseSnapshotDocument(JSON.parse(content), path);
      await upsertIpos(tx, rows.ipos);
      await tx.insert(ipoSnapshots).values(rows.snapshots).onConflictDoNothing();
      await tx.insert(ipoSubscriptions).values(rows.subscriptions).onConflictDoNothing();
      break;
    }
    case "card": {
      const key = researchKey(path);
      if (key === null) break;
      const row = parseCardDocument(JSON.parse(content), key, path);
      await tx.insert(ipoCards).values(row).onConflictDoUpdate({
        target: ipoCards.ipoKey,
        set: replacedSet(ipoCards, row, ["ipoKey"]),
      });
      break;
    }
    case "analysis": {
      const key = researchKey(path);
      if (key === null) break;
      const row = parseAnalysisDocument(content, key);
      await tx.insert(ipoAnalyses).values(row).onConflictDoUpdate({
        target: ipoAnalyses.ipoKey,
        set: { markdown: row.markdown, rhpTextPath: row.rhpTextPath ?? null, contentSha: row.contentSha },
        // Skip unchanged content: the stored hash equals the incoming one.
        setWhere: sql`${ipoAnalyses.contentSha} != ${row.contentSha}`,
      });
      break;
    }
    case "report": {
      const { report, verdicts } = parseReportDocument(JSON.parse(content), path);
      if (reportCommitSha !== null) report.commitSha = reportCommitSha;
      await tx.insert(reports).values(report).onConflictDoUpdate({
        target: [reports.reportDate, reports.session],
        set: replacedSet(reports, report, ["reportDate", "session"]),
      });
      for (const verdict of verdicts) {
        await tx.insert(ipoVerdicts).values(verdict).onConflictDoUpdate({
          target: [ipoVerdicts.reportDate, ipoVerdicts.session, ipoVerdicts.ipoKey],
          set: replacedSet(ipoVerdicts, verdict, ["reportDate", "session", "ipoKey"]),
        });
      }
      break;
    }
    case "outcome": {
      const rows = parseOutcomesDocument(JSON.parse(content));
      for (const row of rows) {
        await tx.insert(ipoOutcomes).values(row).onConflictDoUpdate({
          target: ipoOutcomes.ipoKey,
          set: replacedSet(ipoOutcomes, row, ["ipoKey"]),
        });
      }
      break;
    }
  }
}

/** Removes the rows a deleted research file owns, child first. */
async function deleteFileRows(tx: ImportTx, path: string): Promise<void> {
  const kind = classifyResearchFile(path);
  switch (kind) {
    case "snapshot":
      await tx
        .delete(ipoSubscriptions)
        .where(
          sql`(${ipoSubscriptions.ipoKey}, ${ipoSubscriptions.takenAt}) in
              (select ${ipoSnapshots.ipoKey}, ${ipoSnapshots.takenAt} from ${ipoSnapshots}
               where ${ipoSnapshots.sourceFile} = ${path})`,
        );
      await tx.delete(ipoSnapshots).where(eq(ipoSnapshots.sourceFile, path));
      break;
    case "card":
      await tx.delete(ipoCards).where(eq(ipoCards.sourceFile, path));
      break;
    case "analysis": {
      const key = researchKey(path);
      if (key !== null) await tx.delete(ipoAnalyses).where(eq(ipoAnalyses.ipoKey, key));
      break;
    }
    case "report":
      await tx
        .delete(ipoVerdicts)
        .where(
          sql`(${ipoVerdicts.reportDate}, ${ipoVerdicts.session}) in
              (select ${reports.reportDate}, ${reports.session} from ${reports}
               where ${reports.sourceFile} = ${path})`,
        );
      await tx.delete(reports).where(eq(reports.sourceFile, path));
      break;
    case "outcome":
      // data/outcomes.json owns every ipo_outcomes row.
      await tx.delete(ipoOutcomes);
      break;
    default:
      break;
  }
}

// ---------------------------------------------------------------------------
// One commit, and the rebuild
// ---------------------------------------------------------------------------

/**
 * Imports one commit in a single transaction. A failure rolls back the whole
 * commit — not even rows from the commit's good files survive — records a
 * `failed` row in its own small transaction and returns ok: false, so the run
 * stops there and the next run can retry.
 */
export async function importCommit(db: ImportDb, root: string, sha: string): Promise<CommitOutcome> {
  const research = changedPaths(root, sha).filter((change) => classifyResearchFile(change.path) !== null);
  const files = research.length;
  const startedAt = new Date();
  try {
    await db.transaction(async (tx) => {
      await tx.execute(sql.raw(`select pg_advisory_xact_lock(${ADVISORY_LOCK_KEY})`));
      const contents = await readFilesAt(
        root,
        sha,
        research.filter((change) => change.status !== "D").map((change) => change.path),
      );
      for (const change of research) {
        if (change.status === "D") {
          await deleteFileRows(tx, change.path);
        } else {
          // Reports record the commit that changed them; other kinds ignore it.
          await applyFile(tx, change.path, contents[change.path], sha);
        }
      }
      await recordOk(tx, { sha, files, startedAt, finishedAt: new Date() });
    });
    return { sha, files, ok: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    try {
      await db.transaction(async (tx) => {
        await tx.execute(sql.raw(`select pg_advisory_xact_lock(${ADVISORY_LOCK_KEY})`));
        await recordFailed(tx, { sha, files, startedAt, error: message });
      });
    } catch {
      // The failed row itself could not be written (branch gone, etc.); the
      // caller still needs the outcome.
    }
    return { sha, files, ok: false, error: message };
  }
}

/**
 * The full rebuild: in one transaction, delete the rows of the eight IPO
 * research tables (child first — plain DELETE, never TRUNCATE ... CASCADE, so
 * `stocks` → `watchlist_items` app rows are never pulled in), replay every
 * research file in HEAD's tree — read from HEAD — and record HEAD as imported.
 * Snapshots replay in their chronological (filename) order so the newest merged
 * `ipos` facts win; the replacement tables are order-independent. Stock
 * research joins the rebuild in 015/018.
 */
export async function rebuild(db: ImportDb, root: string): Promise<{ files: number }> {
  const sha = headSha(root);
  const files = listResearchFilesAtHead(root).filter((path) => classifyResearchFile(path) !== null);
  const startedAt = new Date();
  await db.transaction(async (tx) => {
    await tx.execute(sql.raw(`select pg_advisory_xact_lock(${ADVISORY_LOCK_KEY})`));
    await tx.delete(ipoSubscriptions);
    await tx.delete(ipoSnapshots);
    await tx.delete(ipoVerdicts);
    await tx.delete(reports);
    await tx.delete(ipoCards);
    await tx.delete(ipoAnalyses);
    await tx.delete(ipoOutcomes);
    await tx.delete(ipos);

    const contents = await readFilesAt(root, sha, files);
    const snapshots = files.filter((path) => classifyResearchFile(path) === "snapshot");
    for (const path of snapshots) {
      await applyFile(tx, path, contents[path], null);
    }
    for (const path of files) {
      if (classifyResearchFile(path) === "snapshot") continue;
      await applyFile(tx, path, contents[path], lastCommitTouching(root, path));
    }

    await recordOk(tx, { sha, files: files.length, startedAt, finishedAt: new Date() });
  });
  return { files: files.length };
}
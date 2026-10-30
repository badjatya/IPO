import { sql } from "drizzle-orm";
import { ADVISORY_LOCK_KEY, importCommit, rebuild } from "./apply";
import { allMainlineCommits, headSha, mainlineCommitsAfter } from "./git";
import { failedCommitShas, lastOkSha, okCommitShas, recordFailed } from "./log";
import type { ImportDb } from "./types";

// The command resolution: `--rebuild`, an explicit `--from` (or the whole
// history, the test seam), or the default — import the commits after the last
// ok row, one transaction each, stopping at the first failure; when there is
// nothing to resume from (an empty `imports` table, or a rewritten history with
// no ok sha on it) the default command runs the full rebuild instead of
// replaying the whole history one commit at a time (docs/db.md § Import and
// rebuild). A failed commit's content on main never changes, so the default
// command also switches to the rebuild when the first commit to import already
// has a `failed` row and HEAD has moved past it — retrying it would block every
// later commit forever. Every rebuild that fails records a `failed` row for
// HEAD first, exactly as a failed commit does.

export interface RunOptions {
  root: string;
  db: ImportDb;
  rebuild?: boolean;
  /**
   * An explicit starting point: a sha → the commits after it; `null` → the
   * whole first-parent history (the test seam). `undefined` → the default
   * last-ok logic.
   */
  from?: string | null;
  /** Optional per-action logger (the CLI passes console.log). */
  log?: (line: string) => void;
}

export interface RunResult {
  mode: "rebuild" | "incremental";
  ok: boolean;
  commitsImported: number;
  commitsSkipped: number;
  /** The sha the run stopped at, when a commit failed. */
  failedSha?: string;
  error?: string;
}

/**
 * The whole-repo rebuild, and when it throws a `failed` row for HEAD in its own
 * small transaction — exactly as `importCommit` records a failed commit — so a
 * failed rebuild leaves a visible `failed` row behind instead of only an exit
 * code. The error still propagates to the caller, like before.
 */
async function rebuildRecordingFailure(root: string, db: ImportDb): Promise<{ files: number }> {
  try {
    return await rebuild(db, root);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const sha = headSha(root);
    const startedAt = new Date();
    try {
      await db.transaction(async (tx) => {
        await tx.execute(sql.raw(`select pg_advisory_xact_lock(${ADVISORY_LOCK_KEY})`));
        await recordFailed(tx, { sha, files: 0, startedAt, error: message });
      });
    } catch {
      // The failed row itself could not be written (branch gone, etc.); the
      // error still propagates to the caller.
    }
    throw error;
  }
}

export async function runImport(options: RunOptions): Promise<RunResult> {
  const { root, db, log } = options;

  if (options.rebuild) {
    const { files } = await rebuildRecordingFailure(root, db);
    log?.(`rebuild: recreated the ${files} research file(s) at HEAD in one transaction`);
    return { mode: "rebuild", ok: true, commitsImported: 0, commitsSkipped: 0 };
  }

  let commits: string[];
  if (options.from !== undefined) {
    commits =
      options.from === null
        ? allMainlineCommits(root)
        : mainlineCommitsAfter(root, options.from);
  } else {
    const lastOk = await lastOkSha(root, db);
    if (lastOk === undefined) {
      const { files } = await rebuildRecordingFailure(root, db);
      log?.(
        `nothing to resume from (empty imports or rewritten history) — ` +
          `rebuilt the ${files} research file(s) at HEAD in one transaction`,
      );
      return { mode: "rebuild", ok: true, commitsImported: 0, commitsSkipped: 0 };
    }
    commits = mainlineCommitsAfter(root, lastOk);

    // A failed commit's content on main never changes — history is immutable —
    // so retrying it only fails again and blocks every later commit forever.
    // When the first commit to import already has a `failed` row and HEAD is a
    // newer commit (a later push carries the fix), stop retrying it and run the
    // rebuild at HEAD instead, whose tree holds the fixed files. A commit that
    // fails for the first time, or one that is HEAD itself, still retries, so
    // transient failures behave exactly as before (docs/db.md § Import and
    // rebuild).
    if (commits.length > 0) {
      const failedShas = await failedCommitShas(db);
      const first = commits[0];
      if (failedShas.has(first) && first !== headSha(root)) {
        log?.(`commit ${first} failed before; HEAD has moved on, so rebuilding from HEAD`);
        const { files } = await rebuildRecordingFailure(root, db);
        log?.(`rebuilt the ${files} research file(s) at HEAD in one transaction`);
        return { mode: "rebuild", ok: true, commitsImported: 0, commitsSkipped: 0 };
      }
    }
  }

  const okShas = await okCommitShas(db);
  let imported = 0;
  let skipped = 0;
  for (const sha of commits) {
    if (okShas.has(sha)) {
      skipped++;
      log?.(`skipped ${sha}: already imported`);
      continue;
    }
    const outcome = await importCommit(db, root, sha);
    if (!outcome.ok) {
      log?.(`failed ${sha} (${outcome.files} file(s)): ${outcome.error}`);
      return {
        mode: "incremental",
        ok: false,
        commitsImported: imported,
        commitsSkipped: skipped,
        failedSha: sha,
        error: outcome.error,
      };
    }
    imported++;
    log?.(`imported ${sha} (${outcome.files} file(s))`);
  }
  log?.(`import: ${imported} commit(s) imported, ${skipped} already imported`);
  return { mode: "incremental", ok: true, commitsImported: imported, commitsSkipped: skipped };
}
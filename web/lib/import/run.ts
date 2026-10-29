import { importCommit, rebuild } from "./apply";
import { allMainlineCommits, mainlineCommitsAfter } from "./git";
import { lastOkSha, okCommitShas } from "./log";
import type { ImportDb } from "./types";

// The command resolution: `--rebuild`, an explicit `--from` (or the whole
// history, the test seam), or the default — import the commits after the last
// ok row, one transaction each, stopping at the first failure; when there is
// nothing to resume from (an empty `imports` table, or a rewritten history with
// no ok sha on it) the default command runs the full rebuild instead of
// replaying the whole history one commit at a time (docs/db.md § Import and
// rebuild).

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

export async function runImport(options: RunOptions): Promise<RunResult> {
  const { root, db, log } = options;

  if (options.rebuild) {
    const { files } = await rebuild(db, root);
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
      const { files } = await rebuild(db, root);
      log?.(
        `nothing to resume from (empty imports or rewritten history) — ` +
          `rebuilt the ${files} research file(s) at HEAD in one transaction`,
      );
      return { mode: "rebuild", ok: true, commitsImported: 0, commitsSkipped: 0 };
    }
    commits = mainlineCommitsAfter(root, lastOk);
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
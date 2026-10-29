import { eq } from "drizzle-orm";
import { imports } from "@/db/schema";
import { firstParentHistory } from "./git";
import type { ImportDb, ImportTx } from "./types";

// The `imports` bookkeeping rows (docs/db.md § `imports`). The table has no
// sequence column, so "last ok" is found through git: the first sha in
// `git rev-list --first-parent HEAD` (newest first) that has an ok row. Writing
// an ok row upserts over an earlier failed row for the same sha (commit_sha is
// the primary key), so a commit that failed once — transiently, or after its
// files were fixed — imports on a later run.

export interface ImportStamp {
  sha: string;
  files: number;
  startedAt: Date;
  finishedAt?: Date;
  error?: string;
}

/** Every currently-ok sha — used to skip already-imported commits. */
export async function okCommitShas(db: ImportDb): Promise<Set<string>> {
  const rows = await db.select({ commitSha: imports.commitSha }).from(imports).where(eq(imports.status, "ok"));
  return new Set(rows.map((row) => row.commitSha));
}

/**
 * The last imported commit: the newest sha on the first-parent chain that has
 * an ok row. `undefined` when the table is empty or no ok sha is on the current
 * history (rewritten history) — the caller then runs the rebuild.
 */
export async function lastOkSha(root: string, db: ImportDb): Promise<string | undefined> {
  const ok = await okCommitShas(db);
  if (ok.size === 0) return undefined;
  for (const sha of firstParentHistory(root)) {
    if (ok.has(sha)) return sha;
  }
  return undefined;
}

/** Records a successful import inside the commit's own transaction. */
export async function recordOk(tx: ImportTx, stamp: ImportStamp): Promise<void> {
  const finishedAt = stamp.finishedAt ?? new Date();
  await tx
    .insert(imports)
    .values({ commitSha: stamp.sha, startedAt: stamp.startedAt, finishedAt, status: "ok", files: stamp.files })
    .onConflictDoUpdate({
      target: imports.commitSha,
      set: { status: "ok", startedAt: stamp.startedAt, finishedAt, files: stamp.files, error: null },
    });
}

/**
 * Records a failed import in its own small transaction, after the commit's
 * transaction rolled back. `finished_at` stays null, per db.md.
 */
export async function recordFailed(tx: ImportTx, stamp: ImportStamp): Promise<void> {
  await tx
    .insert(imports)
    .values({ commitSha: stamp.sha, startedAt: stamp.startedAt, status: "failed", files: stamp.files, error: stamp.error ?? null })
    .onConflictDoUpdate({
      target: imports.commitSha,
      set: { status: "failed", startedAt: stamp.startedAt, finishedAt: null, files: stamp.files, error: stamp.error ?? null },
    });
}
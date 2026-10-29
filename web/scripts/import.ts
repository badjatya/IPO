#!/usr/bin/env node
// `npm run import` / `npm run import -- --rebuild` — turn the repo's research
// files into rows (docs/db.md § Import and rebuild). Reads the pooled
// DATABASE_URL; the npm scripts load web/.env.local via
// `tsx --env-file-if-exists=.env.local`, and CI / the import Action (009) set
// the variable in the environment instead. Exits non-zero when a commit fails
// (the next run retries from the last ok) or when DATABASE_URL is missing.

import { fileURLToPath } from "node:url";
import { closePool, poolDb } from "@/lib/db";
import { repoRoot } from "@/lib/import/git";
import { runImport } from "@/lib/import/run";

// Helpers (web/scripts) sit one level under the repo root; discovery is from
// this file's own location, never the caller's cwd.
const defaultRoot = repoRoot(fileURLToPath(new URL("..", import.meta.url)));

function usage(exitCode: number) {
  console.error(
    `usage: tsx scripts/import.ts [--rebuild] [--from <sha>] [--root <repo>]\n` +
      `  (default)  import the commits after the last ok row, one transaction each;\n` +
      `             an empty imports table or rewritten history runs the rebuild\n` +
      `  --rebuild  empty the IPO research tables and replay every research file at HEAD\n` +
      `  --from     import only the commits after <sha>, instead of the last ok row\n` +
      `  --root     the repo to import (default: the checkout containing web/scripts)`,
  );
  process.exit(exitCode);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--help") || args.includes("-h")) usage(0);
  const rebuild = args.includes("--rebuild");
  const fromFlag = args.indexOf("--from");
  const from = fromFlag >= 0 ? args[fromFlag + 1] : undefined;
  const rootFlag = args.indexOf("--root");
  const root = rootFlag >= 0 ? args[rootFlag + 1] : defaultRoot;

  if (!process.env.DATABASE_URL) {
    console.error(
      "DATABASE_URL is not set: the npm scripts load web/.env.local (write it with\n" +
        "`neon checkout dev` in web/); CI and the import Action set the variable instead.",
    );
    process.exitCode = 1;
    return;
  }

  try {
    const db = poolDb();
    const result = await runImport({ root, db, rebuild, from: from ?? undefined, log: console.log });
    if (!result.ok) {
      console.error(`import failed on ${result.failedSha}: ${result.error}`);
      console.error("rollback complete — the next run retries from the last ok row");
      process.exitCode = 1;
    }
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  } finally {
    await closePool().catch(() => undefined);
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
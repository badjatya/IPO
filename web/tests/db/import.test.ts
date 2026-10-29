import { createHash } from "node:crypto";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, describe, expect, it } from "vitest";
import { and, eq, sql } from "drizzle-orm";
import * as schema from "@/db/schema";
import { poolDb } from "@/lib/db";
import { classifyResearchFile } from "@/lib/import/files";
import { headSha, listResearchFilesAtHead, readFileAt, repoRoot } from "@/lib/import/git";
import { runImport } from "@/lib/import/run";

// The import's database tests, on the real Neon branch `npm run test:db`
// creates (vitest.db.config.mts; setup.ts refuses to run anywhere else):
// (a) --rebuild twice gives identical per-table row counts, derived from the
//     repo's own files at run time — never hard-coded;
// (b) app rows (users, settings, a watchlist item on a standalone stocks row)
//     survive a rebuild;
// (c) in a temp repo, a commit with a good snapshot and a malformed card leaves
//     no rows, records one failed row and makes the run exit non-zero; when the
//     commit is fixed, the next run imports its data and an ok row upserts over
//     the failed one;
// (d) deleting a report file removes its report + verdict rows while ipos facts
//     survive;
// (e) re-running an already-imported range changes nothing;
// (f) spot-checks of known rows;
// (g) an unchanged ipo_analyses row is not rewritten (its content_sha matches
//     the file, and re-importing leaves its xmin alone).
// The whole-repo rebuild (a, b, f) reads the real checkout's HEAD tree, which
// works in CI's shallow clone (no history walk). Per-commit tests (c, d, e, g)
// use throwaway temp repos. No report.commit_sha assertion against the real
// checkout: a shallow clone gives the graft commit.

const root = repoRoot(process.cwd());
const WEB = fileURLToPath(new URL("../..", import.meta.url));
const db = () => poolDb();

let tempRepos: string[] = [];
function makeRepo() {
  const repo = mkdtempSync(join(tmpdir(), "import-db-"));
  tempRepos.push(repo);
  const git = (args: string[]) => execFileSync("git", args, { cwd: repo, encoding: "utf8" }).trim();
  git(["init", "-q"]);
  git(["symbolic-ref", "HEAD", "refs/heads/main"]);
  git(["config", "user.email", "import-test@example.com"]);
  git(["config", "user.name", "Import Test"]);
  return { repo, git };
}

function write(repo: string, path: string, content: string) {
  const target = join(repo, path);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, content);
}

function commitAll(git: (args: string[]) => string, message: string): string {
  git(["add", "-A"]);
  git(["commit", "-q", "-m", message]);
  return git(["rev-parse", "HEAD"]);
}

afterAll(() => {
  for (const repo of tempRepos) rmSync(repo, { recursive: true, force: true });
});

// Counts queries -----------------------------------------------------------

async function countRows(q: ReturnType<typeof sql>) {
  const result = await db().execute(q);
  return Number(result.rows[0]?.count ?? 0);
}

async function tableCounts() {
  return {
    ipos: await countRows(sql`select count(*)::int as count from ${schema.ipos}`),
    snapshots: await countRows(sql`select count(*)::int as count from ${schema.ipoSnapshots}`),
    subscriptions: await countRows(sql`select count(*)::int as count from ${schema.ipoSubscriptions}`),
    cards: await countRows(sql`select count(*)::int as count from ${schema.ipoCards}`),
    analyses: await countRows(sql`select count(*)::int as count from ${schema.ipoAnalyses}`),
    reports: await countRows(sql`select count(*)::int as count from ${schema.reports}`),
    verdicts: await countRows(sql`select count(*)::int as count from ${schema.ipoVerdicts}`),
    outcomes: await countRows(sql`select count(*)::int as count from ${schema.ipoOutcomes}`),
    imports: await countRows(sql`select count(*)::int as count from ${schema.imports}`),
  };
}

/** The row counts the repo's own files imply, computed without the parsers. */
async function expectedResearchCounts() {
  const sha = headSha(root);
  const files = listResearchFilesAtHead(root);
  const keys = new Set<string>();
  let snapshots = 0;
  let subscriptions = 0;
  let verdicts = 0;
  for (const path of files) {
    const kind = classifyResearchFile(path);
    const doc = JSON.parse(readFileAt(root, sha, path)) as {
      ipos?: Array<{ key?: string; subscription?: Record<string, unknown> }>;
    };
    if (kind === "snapshot") {
      for (const entry of doc.ipos ?? []) {
        keys.add(entry.key ?? "");
        snapshots++;
        subscriptions += Object.keys(entry.subscription ?? {}).length;
      }
    } else if (kind === "report") {
      verdicts += Object.keys((doc as { ipos?: Record<string, unknown> }).ipos ?? {}).length;
    }
  }
  return {
    ipos: keys.size,
    snapshots,
    subscriptions,
    cards: files.filter((path) => classifyResearchFile(path) === "card").length,
    analyses: files.filter((path) => classifyResearchFile(path) === "analysis").length,
    reports: files.filter((path) => classifyResearchFile(path) === "report").length,
    verdicts,
    outcomes: Object.keys(JSON.parse(readFileAt(root, sha, "data/outcomes.json")) as Record<string, unknown>).length,
  };
}

function runCli(args: string[], overrides: Record<string, string> = {}) {
  return spawnSync("npx", ["--no-install", "tsx", "scripts/import.ts", ...args], {
    cwd: WEB,
    env: { ...process.env, ...overrides },
    encoding: "utf8",
  });
}

// Tests --------------------------------------------------------------------

describe("import: whole-repo rebuild on the branch", () => {
  it("rebuilds twice to identical counts that match the repo's own files", async () => {
    const first = await runImport({ root, db: db(), rebuild: true });
    expect(first.ok).toBe(true);
    const afterFirst = await tableCounts();
    const expected = await expectedResearchCounts();
    expect(afterFirst.ipos).toBeGreaterThan(0);
    expect(afterFirst).toMatchObject({ ...expected, imports: 1 });

    const second = await runImport({ root, db: db(), rebuild: true });
    expect(second.ok).toBe(true);
    expect(await tableCounts()).toEqual(afterFirst);
  }, 180_000);

  it("leaves app tables alone through a rebuild", async () => {
    const userId = (
      await db()
        .insert(schema.users)
        .values({ email: "import-test@example.com", name: "Import Test" })
        .returning({ id: schema.users.id })
    )[0]!.id;
    await db()
      .insert(schema.stocks)
      .values({ symbol: "IMPTEST", name: "Import Test Stock", active: false })
      .onConflictDoNothing();
    await db()
      .insert(schema.watchlistItems)
      .values({ userId, symbol: "IMPTEST" })
      .onConflictDoNothing();
    // The seeded settings rows are app rows too; the schema-rules suite asserts
    // their exact set, so leave them untouched beyond a read check.
    const settingsBefore = await db().select().from(schema.settings);
    expect(settingsBefore.length).toBeGreaterThan(0);

    const rebuilt = await runImport({ root, db: db(), rebuild: true });
    expect(rebuilt.ok).toBe(true);
    expect((await db().select().from(schema.users).where(eq(schema.users.id, userId))).length).toBe(1);
    expect((await db().select().from(schema.watchlistItems).where(eq(schema.watchlistItems.symbol, "IMPTEST"))).length).toBe(1);
    expect(await db().select().from(schema.settings)).toEqual(settingsBefore);
  }, 180_000);

  it("spot-checks a snapshot, zetwerk's card, analysis and latest verdict, an override and an outcome", async () => {
    const snap = await db()
      .select()
      .from(schema.ipoSnapshots)
      .where(
        and(
          eq(schema.ipoSnapshots.ipoKey, "sfc-environmental-technologies"),
          eq(schema.ipoSnapshots.sourceFile, "data/snapshots/2026-10-29T0907.json"),
        ),
      );
    expect(snap).toHaveLength(1);
    expect(new Date(snap[0]!.takenAt!).getTime()).toBe(new Date("2026-10-29T09:07+05:30").getTime());
    expect(Number(snap[0]!.gmp)).toBe(10);
    expect(snap[0]!.sourceFile).toBe("data/snapshots/2026-10-29T0907.json");

    const card = await db().select().from(schema.ipoCards).where(eq(schema.ipoCards.ipoKey, "zetwerk"));
    expect(card[0]!.verdict).toBe("neutral");
    expect(card[0]!.sourceFile).toBe("analysis/zetwerk.json");

    // The most recent report that carried a zetwerk call, derived from the repo.
    const sha = headSha(root);
    const reportPaths = listResearchFilesAtHead(root)
      .filter((path) => classifyResearchFile(path) === "report")
      .toSorted();
    let expectedVerdict: string | undefined;
    let expectedDate: string | undefined;
    let expectedSession: "AM" | "PM" | undefined;
    for (const path of reportPaths.toReversed()) {
      const doc = JSON.parse(readFileAt(root, sha, path)) as {
        date?: string;
        session?: string;
        ipos?: Record<string, { verdict?: string }>;
      };
      const verdictValue = doc.ipos?.["zetwerk"]?.verdict;
      if (verdictValue !== undefined) {
        expectedVerdict = verdictValue;
        expectedDate = doc.date;
        expectedSession = doc.session as "AM" | "PM";
        break;
      }
    }
    expect(expectedVerdict).toBeDefined();
    const verdictRow = await db()
      .select()
      .from(schema.ipoVerdicts)
      .where(
        and(
          eq(schema.ipoVerdicts.ipoKey, "zetwerk"),
          eq(schema.ipoVerdicts.reportDate, expectedDate!),
          eq(schema.ipoVerdicts.session, expectedSession!),
        ),
      );
    expect(verdictRow).toHaveLength(1);
    expect(verdictRow[0]!.verdict).toBe(expectedVerdict);

    const overrides = await db()
      .select({ overrides: schema.ipoVerdicts.overrides })
      .from(schema.ipoVerdicts)
      .where(
        and(
          eq(schema.ipoVerdicts.ipoKey, "hd-fire-protect"),
          eq(schema.ipoVerdicts.reportDate, "2026-10-13"),
          eq(schema.ipoVerdicts.session, "AM"),
        ),
      );
    expect(Object.keys(overrides[0]!.overrides ?? {})).toEqual(expect.arrayContaining(["summary", "financials", "quota"]));

    const outcome = await db().select().from(schema.ipoOutcomes).where(eq(schema.ipoOutcomes.ipoKey, "hd-fire-protect"));
    expect(Number(outcome[0]!.subRetail)).toBe(20.83);

    const analysis = await db().select().from(schema.ipoAnalyses).where(eq(schema.ipoAnalyses.ipoKey, "zetwerk"));
    expect(analysis[0]!.rhpTextPath).toBe("analysis/rhp/zetwerk.txt");
    expect(analysis[0]!.contentSha).toBe(
      createHash("sha256").update(readFileAt(root, sha, "analysis/zetwerk.md")).digest("hex"),
    );
  }, 180_000);
});

describe("import: per-commit runs against a temp repo", () => {
  it("(c) a bad commit leaves no rows and fails the run; a fixed commit imports and flips its row to ok", async () => {
    const { repo, git } = makeRepo();
    const snapshotA = JSON.stringify({
      generated_at: "2026-10-29T09:07+05:30",
      ipos: [
        { key: "sfc-environmental-technologies", name: "SFC Environmental Technologies", phase: "closing_today" },
      ],
    });
    write(repo, "data/snapshots/2026-10-29T0907.json", snapshotA);
    const a = commitAll(git, "a: one snapshot");

    const first = await runImport({ root: repo, db: db(), from: null });
    expect(first.ok).toBe(true);
    expect(first.commitsImported).toBe(1);
    expect((await tableCounts()).imports).toBeGreaterThan(0);
    const okRows = await db().select().from(schema.imports).where(eq(schema.imports.status, "ok"));
    expect(okRows.map((row) => row.commitSha)).toContain(a);
    const snapshotsAfterA = (await tableCounts()).snapshots;

    // b: a good snapshot plus a malformed card — the whole commit must roll back.
    const snapshotB = JSON.stringify({
      generated_at: "2026-10-28T09:07+05:30",
      ipos: [{ key: "sfc-environmental-technologies", name: "SFC Environmental Technologies", phase: "open" }],
    });
    write(repo, "data/snapshots/2026-10-28T0907.json", snapshotB);
    write(
      repo,
      "analysis/sfc-environmental-technologies.json",
      JSON.stringify({ name: "SFC Environmental Technologies", source: "rhp", verdict: "buy", verdict_text: "Buy", anchor_grade: "strong" }),
    );
    const bad = commitAll(git, "b: good snapshot + malformed card");

    const failed = runCli(["--root", repo]);
    expect(failed.status).not.toBe(0);
    expect(failed.stdout + failed.stderr).toContain("verdict");

    const afterFailure = await tableCounts();
    expect(afterFailure.snapshots).toBe(snapshotsAfterA); // the good snapshot rolled back too
    const failedRows = await db().select().from(schema.imports).where(eq(schema.imports.status, "failed"));
    expect(failedRows).toHaveLength(1);
    expect(failedRows[0]!.commitSha).toBe(bad);
    expect(failedRows[0]!.error).toContain("verdict");

    // Fix the commit (history rewritten, as the plan documents for a bad file)
    // and pretend the fixed commit itself once failed transiently, so the next
    // run's ok write must upsert over that failed row.
    write(
      repo,
      "analysis/sfc-environmental-technologies.json",
      JSON.stringify({ name: "SFC Environmental Technologies", source: "rhp", verdict: "neutral", verdict_text: "Neutral", anchor_grade: "strong" }),
    );
    git(["add", "-A"]);
    git(["commit", "-q", "--amend", "--no-edit", "-m", "b: fixed card"]);
    const fixed = git(["rev-parse", "HEAD"]);
    expect(fixed).not.toBe(bad);
    await db()
      .insert(schema.imports)
      .values({ commitSha: fixed, startedAt: new Date(), status: "failed", error: "transient" })
      .onConflictDoNothing();

    const retried = runCli(["--root", repo]);
    expect(retried.status).toBe(0);

    const afterFix = await tableCounts();
    expect(afterFix.snapshots).toBe(snapshotsAfterA + 1); // b's snapshot landed
    const card = await db().select().from(schema.ipoCards).where(eq(schema.ipoCards.ipoKey, "sfc-environmental-technologies"));
    expect(card[0]!.verdict).toBe("neutral");
    const fixedRow = await db().select().from(schema.imports).where(eq(schema.imports.commitSha, fixed));
    expect(fixedRow).toHaveLength(1);
    expect(fixedRow[0]!.status).toBe("ok");
    expect(fixedRow[0]!.error).toBeNull(); // the failed row was upserted
  }, 180_000);

  it("(d) a deleted report file's rows go with it; ipos facts survive", async () => {
    const { repo, git } = makeRepo();
    write(repo, "data/snapshots/2026-10-29T0907.json", JSON.stringify({
      generated_at: "2026-10-29T09:07+05:30",
      ipos: [
        { key: "sfc-environmental-technologies", name: "SFC", phase: "closing_today" },
        { key: "bls-polymers", name: "BLS", phase: "closing_today" },
      ],
    }));
    write(repo, "reports/2026-10-29-pm.json", JSON.stringify({
      date: "2026-10-29",
      session: "PM",
      headline: "x",
      ipos: { "sfc-environmental-technologies": { verdict: "listing_gains", verdict_text: "Listing gains only" } },
      notes: [],
    }));
    commitAll(git, "a: snapshot + report");

    const first = await runImport({ root: repo, db: db(), from: null });
    expect(first.ok).toBe(true);
    const reportsAfterA = (await tableCounts()).reports;
    expect(reportsAfterA).toBe(1);
    const verdictsAfterA = (await tableCounts()).verdicts;
    expect(verdictsAfterA).toBe(1);

    git(["rm", "-q", "reports/2026-10-29-pm.json"]);
    commitAll(git, "b: delete the report");

    const second = await runImport({ root: repo, db: db(), from: null });
    expect(second.ok).toBe(true);
    expect(second.commitsImported).toBe(1); // a was skipped as already ok

    const counts = await tableCounts();
    expect(counts.reports).toBe(0);
    expect(counts.verdicts).toBe(0);
    // The snapshot still owns the ipos facts.
    const ipo = await db().select().from(schema.ipos).where(eq(schema.ipos.key, "sfc-environmental-technologies"));
    expect(ipo).toHaveLength(1);
    expect(counts.ipos).toBe(2);
  }, 180_000);

  it("(e) re-running an already-imported range changes nothing", async () => {
    const { repo, git } = makeRepo();
    write(repo, "data/snapshots/2026-10-29T0907.json", JSON.stringify({
      generated_at: "2026-10-29T09:07+05:30",
      ipos: [{ key: "sfc-environmental-technologies", name: "SFC", phase: "closing_today" }],
    }));
    commitAll(git, "a: snapshot");
    const first = await runImport({ root: repo, db: db(), from: null });
    expect(first.ok).toBe(true);
    const afterFirst = await tableCounts();

    const second = await runImport({ root: repo, db: db(), from: null });
    expect(second.ok).toBe(true);
    expect(second.commitsImported).toBe(0);
    expect(second.commitsSkipped).toBe(1);
    expect(await tableCounts()).toEqual(afterFirst);
  }, 180_000);

  it("(g) an unchanged ipo_analyses row is not rewritten", async () => {
    const { repo, git } = makeRepo();
    const md = "# SFC Environmental Technologies\n\nAnalysis text.\n";
    write(repo, "data/snapshots/2026-10-29T0907.json", JSON.stringify({
      generated_at: "2026-10-29T09:07+05:30",
      ipos: [{ key: "sfc-environmental-technologies", name: "SFC", phase: "closing_today" }],
    }));
    write(repo, "analysis/sfc-environmental-technologies.md", md);
    commitAll(git, "a: snapshot + analysis");

    const first = await runImport({ root: repo, db: db(), from: null });
    expect(first.ok).toBe(true);
    const rows = await db().select().from(schema.ipoAnalyses).where(eq(schema.ipoAnalyses.ipoKey, "sfc-environmental-technologies"));
    expect(rows).toHaveLength(1);
    expect(rows[0]!.contentSha).toBe(createHash("sha256").update(md).digest("hex"));
    expect(rows[0]!.rhpTextPath).toBe("analysis/rhp/sfc-environmental-technologies.txt");

    // A later commit touches only a snapshot; re-importing every commit leaves
    // the analysis row untouched (its xmin — the row's last write — is stable).
    write(repo, "data/snapshots/2026-10-29T1913.json", JSON.stringify({
      generated_at: "2026-10-29T19:13+05:30",
      ipos: [{ key: "sfc-environmental-technologies", name: "SFC", phase: "closing_today", gmp: 8 }],
    }));
    commitAll(git, "b: a later snapshot");

    const second = await runImport({ root: repo, db: db(), from: null });
    expect(second.ok).toBe(true);
    expect(second.commitsImported).toBe(1);

    const xmin = async () => {
      const result = await db().execute(sql`select xmin::text as xmin from ${schema.ipoAnalyses} where ${schema.ipoAnalyses.ipoKey} = 'sfc-environmental-technologies'`);
      return result.rows[0]!.xmin as string;
    };
    const before = await xmin();

    const third = await runImport({ root: repo, db: db(), from: null });
    expect(third.ok).toBe(true);
    expect(third.commitsImported).toBe(0);
    expect(await xmin()).toBe(before);
    const after = await db().select({ contentSha: schema.ipoAnalyses.contentSha }).from(schema.ipoAnalyses);
    expect(after[0]!.contentSha).toBe(createHash("sha256").update(md).digest("hex"));
  }, 180_000);

  it("(h) an edit that drops an entry removes its rows, matching a rebuild", async () => {
    const { repo, git } = makeRepo();
    write(repo, "data/snapshots/2026-10-29T0907.json", JSON.stringify({
      generated_at: "2026-10-29T09:07+05:30",
      ipos: [
        { key: "sfc-environmental-technologies", name: "SFC", phase: "closing_today" },
        { key: "bls-polymers", name: "BLS", phase: "closing_today" },
      ],
    }));
    write(repo, "data/outcomes.json", JSON.stringify({
      "sfc-environmental-technologies": { symbol: "SFCTECH", listing_date: "2026-11-04", issue_price: 330, listing_price: 350 },
      "bls-polymers": { symbol: "BLS", listing_date: "2026-11-04", issue_price: 200, listing_price: 210 },
    }));
    write(repo, "reports/2026-10-29-pm.json", JSON.stringify({
      date: "2026-10-29",
      session: "PM",
      headline: "x",
      ipos: {
        "sfc-environmental-technologies": { verdict: "listing_gains", verdict_text: "Listing gains only" },
        "bls-polymers": { verdict: "listing_gains", verdict_text: "Listing gains only" },
      },
      notes: [],
    }));
    commitAll(git, "a: snapshot + report with two IPOs + two outcomes");

    const first = await runImport({ root: repo, db: db(), from: null });
    expect(first.ok).toBe(true);
    const afterFirst = await tableCounts();
    expect(afterFirst.verdicts).toBe(2);
    expect(afterFirst.outcomes).toBe(2);

    // b rewrites the report without one IPO and outcomes.json without one key.
    write(repo, "reports/2026-10-29-pm.json", JSON.stringify({
      date: "2026-10-29",
      session: "PM",
      headline: "x",
      ipos: { "bls-polymers": { verdict: "listing_gains", verdict_text: "Listing gains only" } },
      notes: [],
    }));
    write(repo, "data/outcomes.json", JSON.stringify({
      "bls-polymers": { symbol: "BLS", listing_date: "2026-11-04", issue_price: 200, listing_price: 210 },
    }));
    commitAll(git, "b: report and outcomes drop one IPO each");

    const second = await runImport({ root: repo, db: db(), from: null });
    expect(second.ok).toBe(true);
    const afterSecond = await tableCounts();
    expect(afterSecond.verdicts).toBe(1);
    expect(afterSecond.outcomes).toBe(1);
    const sfcVerdict = await db()
      .select()
      .from(schema.ipoVerdicts)
      .where(eq(schema.ipoVerdicts.ipoKey, "sfc-environmental-technologies"));
    expect(sfcVerdict).toHaveLength(0);

    // Per-commit mode now converges to exactly the file state, like a rebuild.
    const rebuilt = await runImport({ root: repo, db: db(), rebuild: true });
    expect(rebuilt.ok).toBe(true);
    expect(await tableCounts()).toEqual(afterSecond);
  }, 180_000);

  it("(i) one commit can first introduce an IPO with its card, analysis and report", async () => {
    const { repo, git } = makeRepo();
    // A single commit whose paths git lists in path order (analysis/ < data/ <
    // reports/), where the snapshot first creates the ipos row that the card's
    // and verdict's foreign keys need — the real shape of the routine commits
    // the review reproduced (ffdb3cb, 6632e26, 07abccd, f35a790, 6962cca).
    write(repo, "analysis/m-k-sons-fine-jewels.md", "# M K Sons Fine Jewels\n\nAnalysis text.\n");
    write(
      repo,
      "analysis/m-k-sons-fine-jewels.json",
      JSON.stringify({ name: "M K Sons", source: "rhp", verdict: "neutral", verdict_text: "Neutral", anchor_grade: "strong" }),
    );
    write(repo, "data/snapshots/2026-10-23T1908.json", JSON.stringify({
      generated_at: "2026-10-23T19:08+05:30",
      ipos: [{ key: "m-k-sons-fine-jewels", name: "M K Sons", phase: "open" }],
    }));
    write(repo, "reports/2026-10-23-pm.json", JSON.stringify({
      date: "2026-10-23",
      session: "PM",
      headline: "x",
      ipos: { "m-k-sons-fine-jewels": { verdict: "neutral", verdict_text: "Neutral" } },
      notes: [],
    }));
    commitAll(git, "a: snapshot, card, analysis and report in one commit");

    const result = await runImport({ root: repo, db: db(), from: null });
    expect(result.ok).toBe(true);
    const counts = await tableCounts();
    expect(counts.ipos).toBe(1);
    expect(counts.cards).toBe(1);
    expect(counts.analyses).toBe(1);
    expect(counts.reports).toBe(1);
    expect(counts.verdicts).toBe(1);
  }, 180_000);
});

describe("import: CLI", () => {
  it("exits non-zero with a clear message when DATABASE_URL is unset", () => {
    const result = runCli(["--root", root], { DATABASE_URL: "" });
    expect(result.status).not.toBe(0);
    expect(result.stdout + result.stderr).toContain("DATABASE_URL is not set");
  });

  it("exits with usage (code 2) when a value flag has no value", () => {
    // Without the check, `--from` would read `undefined` and silently run the
    // default command (a rebuild, for an empty imports table) on the repo root.
    for (const args of [["--from"], ["--root"], ["--from", "--rebuild"], ["--root", "--rebuild"]]) {
      const result = runCli(args, { DATABASE_URL: "postgres://unused" });
      expect(result.status).toBe(2);
      expect(result.stdout + result.stderr).toContain("usage");
    }
  });
});
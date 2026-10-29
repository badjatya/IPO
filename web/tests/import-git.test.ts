import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  allMainlineCommits,
  changedPaths,
  firstParentHistory,
  headSha,
  lastCommitTouching,
  listResearchFilesAtHead,
  mainlineCommitsAfter,
  readFileAt,
  readFilesAt,
  repoRoot,
} from "@/lib/import/git";
import { classifyResearchFile, researchKey } from "@/lib/import/files";

// The git layer against a throwaway repo the test builds from copies of real
// repo files (a snapshot, a card, a report, data/outcomes.json), across
// commits that modify, side-branch with --no-ff and delete. It never touches
// this repo's history, so it works in CI's shallow clone (fetch-depth: 1).

const SNAPSHOT = "data/snapshots/2026-10-29T0907.json";
const SIDE_SNAPSHOT = "data/snapshots/2026-10-23T1908.json";
const CARD = "analysis/zetwerk.json";
const REPORT = "reports/2026-10-13-am.json";
const OUTCOMES = "data/outcomes.json";

let repo: string;
let c1: string;
let c2: string;
let side: string;
let merge: string;
let c3: string;
let originalReport: string;
let changedReport: string;

function git(args: string[]): string {
  return execFileSync("git", args, { cwd: repo, encoding: "utf8" }).trim();
}

function commit(message: string): string {
  git(["add", "-A"]);
  git(["commit", "-q", "-m", message]);
  return headSha(repo);
}

function copyRealFile(path: string) {
  const root = repoRoot();
  const content = readFileSync(join(root, path), "utf8");
  const target = join(repo, path);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, content);
}

beforeAll(() => {
  repo = mkdtempSync(join(tmpdir(), "import-git-"));
  git(["init", "-q"]);
  git(["symbolic-ref", "HEAD", "refs/heads/main"]);
  git(["config", "user.email", "import-test@example.com"]);
  git(["config", "user.name", "Import Test"]);

  originalReport = readFileSync(join(repoRoot(), REPORT), "utf8");
  copyRealFile(SNAPSHOT);
  copyRealFile(CARD);
  copyRealFile(REPORT);
  copyRealFile(OUTCOMES);
  c1 = commit("c1: the first research files");

  // c2 modifies the report — the same path, a different version.
  const parsed = JSON.parse(originalReport) as { headline: string };
  changedReport = JSON.stringify({ ...parsed, headline: "changed for c2" }, null, 1);
  writeFileSync(join(repo, REPORT), changedReport);
  c2 = commit("c2: tweak the report");

  // A side branch with one file, merged --no-ff: its commit is not on main's
  // first-parent chain, but its file reaches HEAD through the merge.
  git(["checkout", "-q", "-b", "side"]);
  copyRealFile(SIDE_SNAPSHOT);
  side = commit("side: one more snapshot");
  git(["checkout", "-q", "main"]);
  git(["merge", "-q", "--no-ff", "side", "-m", "merge side"]);
  merge = headSha(repo);

  // c3 deletes the report — a status-D change.
  git(["rm", "-q", REPORT]);
  c3 = commit("c3: delete the report");
});

afterAll(() => {
  rmSync(repo, { recursive: true, force: true });
});

describe("repoRoot", () => {
  it("finds the checkout root from web/scripts", () => {
    expect(repoRoot(join(process.cwd(), "scripts"))).toBe(repoRoot());
  });
});

describe("classifyResearchFile", () => {
  it("maps the five research kinds", () => {
    expect(classifyResearchFile(SNAPSHOT)).toBe("snapshot");
    expect(classifyResearchFile(CARD)).toBe("card");
    expect(classifyResearchFile("analysis/zetwerk.md")).toBe("analysis");
    expect(classifyResearchFile(REPORT)).toBe("report");
    expect(classifyResearchFile(OUTCOMES)).toBe("outcome");
  });

  it("ignores everything the import does not own", () => {
    for (const path of [
      "data/latest.json",
      "data/latest.md",
      "data/stocks/HDFCBANK/analysis.json",
      "analysis/rhp/zetwerk.txt",
      "reports/2026-10-13-am.html",
      "reports/2026-10-13-am.txt",
      "reports/2026-10-12-pm.md",
      "README.md",
    ]) {
      expect(classifyResearchFile(path)).toBeNull();
    }
  });

  it("derives the card/analysis key from the path", () => {
    expect(researchKey(CARD)).toBe("zetwerk");
    expect(researchKey("analysis/zetwerk.md")).toBe("zetwerk");
    expect(researchKey(SNAPSHOT)).toBeNull();
    expect(researchKey("analysis/rhp/zetwerk.txt")).toBeNull();
  });
});

describe("mainlineCommitsAfter", () => {
  it("walks only the first-parent chain, in order, and skips the side commit", () => {
    expect(mainlineCommitsAfter(repo, c1)).toEqual([c2, merge, c3]);
  });

  it("lists the whole history oldest-first and newest-first", () => {
    expect(allMainlineCommits(repo)).toEqual([c1, c2, merge, c3]);
    expect(firstParentHistory(repo)).toEqual(allMainlineCommits(repo).toReversed());
  });
});

describe("changedPaths", () => {
  it("shows the adds of the first commit", () => {
    const changes = changedPaths(repo, c1);
    const paths = changes.map((change) => `${change.status}\t${change.path}`).toSorted();
    expect(paths).toEqual(
      [
        `A\t${CARD}`,
        `A\t${OUTCOMES}`,
        `A\t${SNAPSHOT}`,
        `A\t${REPORT}`,
      ].toSorted(),
    );
  });

  it("shows the modification in c2", () => {
    expect(changedPaths(repo, c2)).toEqual([{ status: "M", path: REPORT }]);
  });

  it("shows a --no-ff merge as the files it brought in, applied once", () => {
    // `git diff M^1 M` shows the merge's total change — here the side branch's
    // one file — which is exactly what the import applies at the merge commit.
    expect(changedPaths(repo, merge)).toEqual([{ status: "A", path: SIDE_SNAPSHOT }]);
  });

  it("shows the deletion in c3 with status D", () => {
    expect(changedPaths(repo, c3)).toEqual([{ status: "D", path: REPORT }]);
  });
});

describe("per-commit reads", () => {
  it("reads each commit's own version of a changed file", () => {
    expect(readFileAt(repo, c1, REPORT)).toBe(originalReport);
    expect(readFileAt(repo, c2, REPORT)).toBe(changedReport);
    expect(changedReport).not.toBe(originalReport);
  });

  it("batches reads with git cat-file --batch", async () => {
    const files = [SNAPSHOT, CARD, REPORT, OUTCOMES];
    const batched = await readFilesAt(repo, c1, files);
    for (const path of files) {
      expect(batched[path]).toBe(readFileAt(repo, c1, path));
    }
    // A path absent from the commit is absent from the result, not an error.
    expect(await readFilesAt(repo, c1, ["analysis/never-existed.json"])).toEqual({});
  });

  it("ignores the working tree (the temp repo edits c2's report on disk)", () => {
    // The working tree currently holds c3's state: the report is deleted there,
    // while c1's version must still come back from git objects.
    expect(readFileAt(repo, c1, REPORT)).toBe(originalReport);
  });
});

describe("HEAD listing", () => {
  it("lists HEAD's tree, including merged-side files, without the deleted report", () => {
    const files = listResearchFilesAtHead(repo);
    expect(files).toContain(SNAPSHOT);
    expect(files).toContain(SIDE_SNAPSHOT);
    expect(files).toContain(CARD);
    expect(files).toContain(OUTCOMES);
    expect(files).not.toContain(REPORT);
  });
});

describe("lastCommitTouching", () => {
  it("reports the deletion commit for a deleted path and the add for an unchanged one", () => {
    expect(lastCommitTouching(repo, REPORT)).toBe(c3);
    expect(lastCommitTouching(repo, CARD)).toBe(c1);
    expect(lastCommitTouching(repo, SIDE_SNAPSHOT)).toBe(side);
  });
});
import { execFileSync, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

// Git access for the import (docs/db.md § Import and rebuild). Every helper
// takes the repo root so tests can point them at a throwaway temp repo; the CLI
// discovers the root from its own location (web/scripts) via `repoRoot()`, so
// the import has no cwd dependence. All reads go through git objects — the
// commit being imported, or HEAD — never the working tree, so an old commit
// stores that commit's version of a file and a rebuild records HEAD while
// reading HEAD (immune to a dirty working tree).

/** The well-known empty-tree hash (`git hash-object -t tree /dev/null`). */
export const EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904";

/**
 * The repo root: the nearest ancestor of `fromDir` that holds a `.git` entry
 * (a directory in a plain clone, a `gitdir:` file in a linked worktree).
 * `fromDir` defaults to the caller's cwd; the CLI passes its own script dir.
 */
export function repoRoot(fromDir: string = process.cwd()): string {
  let dir = resolve(fromDir);
  for (;;) {
    if (existsSync(join(dir, ".git"))) return dir;
    const parent = dirname(dir);
    if (parent === dir) {
      throw new Error(`no git repository found at or above ${fromDir}`);
    }
    dir = parent;
  }
}

function git(root: string, args: string[]): string {
  try {
    return execFileSync("git", args, {
      cwd: root,
      encoding: "utf8",
      maxBuffer: 128 * 1024 * 1024,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    const stderr = (error as { stderr?: Buffer }).stderr?.toString().trim();
    throw new Error(`git ${args.join(" ")} failed${stderr ? `: ${stderr}` : ""}`, { cause: error });
  }
}

/** HEAD's full sha. */
export function headSha(root: string): string {
  return git(root, ["rev-parse", "HEAD"]).trim();
}

const EMPTY_LINE = /^\s*$/;

function splitLines(out: string): string[] {
  return out
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => !EMPTY_LINE.test(line));
}

/**
 * The commits to import: main's first-parent chain after `from`, oldest first.
 * Side-branch commits are never applied out of order and each merge appears
 * once (`git rev-list --first-parent --reverse <from>..HEAD`).
 */
export function mainlineCommitsAfter(root: string, from: string): string[] {
  return splitLines(git(root, ["rev-list", "--first-parent", "--reverse", `${from}..HEAD`]));
}

/** Every commit on the first-parent chain, oldest first (the whole history). */
export function allMainlineCommits(root: string): string[] {
  return splitLines(git(root, ["rev-list", "--first-parent", "--reverse", "HEAD"]));
}

/** The first-parent chain, newest first — the order "last ok" is looked up in. */
export function firstParentHistory(root: string): string[] {
  return splitLines(git(root, ["rev-list", "--first-parent", "HEAD"]));
}

export interface Change {
  status: "A" | "M" | "D" | "T";
  path: string;
}

/**
 * The paths a commit changed, diffed against its first parent (`--no-renames`,
 * so a rename is a delete plus an add). A root commit is diffed against the
 * empty tree. `git show --name-only` on a merge lists only conflicted paths,
 * which is why the diff is explicit.
 */
export function changedPaths(root: string, sha: string): Change[] {
  let base: string;
  try {
    base = git(root, ["rev-parse", `${sha}^1`]).trim();
  } catch {
    base = EMPTY_TREE;
  }
  const out = git(root, ["diff", "--name-status", "--no-renames", base, sha]);
  return splitLines(out)
    .map((line) => {
      const tab = line.indexOf("\t");
      if (tab === -1) throw new Error(`unparseable git diff line: ${line}`);
      return { status: line.slice(0, tab) as Change["status"], path: line.slice(tab + 1) };
    })
    .filter((change) => ["A", "M", "D", "T"].includes(change.status));
}

/** One file's content at a commit — byte-exact, never trimmed. */
export function readFileAt(root: string, sha: string, path: string): string {
  return git(root, ["show", `${sha}:${path}`]);
}

/**
 * Many files at one commit, batched through `git cat-file --batch` (one process
 * instead of one per snapshot-heavy commit). Returns an object keyed by path;
 * a path absent from the commit is absent from the result. Used only for paths
 * that exist at `sha`, so misses mean a genuinely broken tree.
 */
export function readFilesAt(root: string, sha: string, paths: string[]): Promise<Record<string, string>> {
  if (paths.length === 0) return Promise.resolve({});
  return new Promise((resolvePromise, reject) => {
    const child = spawn("git", ["cat-file", "--batch"], { cwd: root, stdio: ["pipe", "pipe", "pipe"] });
    const chunks: Buffer[] = [];
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => chunks.push(chunk));
    child.stderr.on("data", (chunk: Buffer) => (stderr += chunk.toString()));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`git cat-file --batch failed (exit ${code}): ${stderr.trim()}`));
        return;
      }
      try {
        resolvePromise(parseBatch(Buffer.concat(chunks), paths));
      } catch (error) {
        reject(error);
      }
    });
    child.stdin.end(paths.map((path) => `${sha}:${path}`).join("\n") + "\n");
  });
}

function parseBatch(buf: Buffer, paths: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  let i = 0;
  for (const path of paths) {
    // Header: `<oid> <type> <size>\n`, or `<oid> missing\n` for a bad path.
    const nl = buf.indexOf(0x0a, i);
    if (nl === -1) throw new Error(`git cat-file --batch ran out of output for ${path}`);
    const header = buf.subarray(i, nl).toString("utf8");
    i = nl + 1;
    const parts = header.split(" ");
    if (parts.length === 2 && parts[1] === "missing") continue;
    if (parts.length !== 3) throw new Error(`git cat-file --batch header: ${header}`);
    const size = Number(parts[2]);
    if (!Number.isInteger(size) || size < 0) throw new Error(`git cat-file --batch size: ${header}`);
    const content = buf.subarray(i, i + size);
    i += size;
    // cat-file terminates each record with a newline unless the content already
    // ends with one; consuming one here is right under either behaviour.
    if (buf[i] === 0x0a) i++;
    out[path] = content.toString("utf8");
  }
  return out;
}

/**
 * Every file in HEAD's tree (`git ls-tree -r`, not `git ls-files`, so staged
 * changes and a dirty working tree are invisible to the rebuild).
 */
export function listResearchFilesAtHead(root: string): string[] {
  return splitLines(git(root, ["ls-tree", "-r", "--name-only", "HEAD"]));
}

/** The last commit on HEAD's history that touched `path`. */
export function lastCommitTouching(root: string, path: string): string | null {
  const out = git(root, ["log", "-1", "--format=%H", "--", path]);
  const sha = out.trim();
  return sha === "" ? null : sha;
}
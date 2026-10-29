#!/usr/bin/env node
// `npm run test:db` — build the full schema on a fresh, short-lived, schema-only
// Neon branch and run the database tests against it (docs/db.md § Migrations and
// environments). The branch is created from the project's default branch with
// `init_source: "schema-only"` and `expires_at` set to now + 1 day, the `public`
// and `drizzle` schemas are dropped (then `public` recreated) so the migrations
// demonstrably build an empty database, `drizzle-kit migrate` runs over the
// branch's unpooled URL, the db tests run over the pooled URL with
// `NEON_TEST_BRANCH_ID` set, and exactly the branch this run created is deleted
// in a `finally`. The pure helpers below are imported by the offline unit test.
//
// Refuses to run without NEON_API_KEY / NEON_PROJECT_ID, and refuses to delete
// the project's default branch or anything named `dev`.

import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";

const API = "https://console.neon.tech/api/v2";
const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

// --- pure helpers (offline-tested in tests/neon-branch.test.ts) -----------------

/** ISO timestamp for now + `days` days — Neon's `expires_at`. */
export function expiryStamp(now = new Date(), days = 1) {
  return new Date(now.getTime() + days * 24 * 60 * 60 * 1000).toISOString();
}

/**
 * True when a branch must never be deleted: the project's default branch, or the
 * long-lived local `dev` branch (web/neon.ts).
 */
export function isProtectedBranch(branch, { defaultBranchId, defaultBranchName } = {}) {
  if (!branch) return false;
  const name = typeof branch.name === "string" ? branch.name.toLowerCase() : "";
  return (
    (defaultBranchId !== undefined && branch.id === defaultBranchId) ||
    name === "dev" ||
    (defaultBranchName !== undefined &&
      typeof branch.name === "string" &&
      branch.name === defaultBranchName)
  );
}

/**
 * The project's default branch: the Neon API v2 Branch object marks it with
 * `default: true` (`is_default` and `primary` are not fields the API sends).
 * Returns undefined when no branch carries the flag.
 */
export function findDefaultBranch(branches) {
  return (branches ?? []).find((branch) => branch.default === true);
}

/**
 * Neon's pooled host is the direct host with `-pooler` before the region
 * (`ep-abc-123.us-east-2.aws.neon.tech` → `ep-abc-123-pooler.us-east-2.aws.neon.tech`).
 * The tests run over the pooled URL, migrations over the direct one.
 */
export function buildPooledUri(unpooledUri) {
  const url = new URL(unpooledUri);
  if (url.hostname.includes("-pooler.")) return url.toString();
  const dot = url.hostname.indexOf(".");
  if (dot === -1) {
    throw new Error(`cannot build a pooled URI from host "${url.hostname}"`);
  }
  url.hostname = `${url.hostname.slice(0, dot)}-pooler${url.hostname.slice(dot)}`;
  return url.toString();
}

/** Build a connection URI from the create-branch response's parts (fallback). */
export function buildUriFromParts({ endpointHost, roleName, rolePassword, databaseName }) {
  if (!endpointHost || !roleName || !rolePassword || !databaseName) {
    throw new Error("cannot build a connection URI from incomplete branch parts");
  }
  return `postgresql://${encodeURIComponent(roleName)}:${encodeURIComponent(rolePassword)}@${endpointHost}/${databaseName}?sslmode=require`;
}

// --- harness --------------------------------------------------------------------

async function api(path, init, apiKey) {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json", ...init?.headers },
  });
  const text = await response.text();
  let body;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = {};
  }
  if (!response.ok) {
    const detail = body.message ?? text ?? response.statusText;
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${response.status}): ${detail}`);
  }
  return body;
}

async function main() {
  const apiKey = process.env.NEON_API_KEY;
  const projectId = process.env.NEON_PROJECT_ID;
  if (!apiKey || !projectId) {
    console.error(
      "test:db needs NEON_API_KEY and NEON_PROJECT_ID (CI secrets, H06). Refusing to run without them \
— the db tests must never touch the `dev` branch by accident.",
    );
    process.exit(2);
  }

  const branchesRes = await api(`/projects/${projectId}/branches`, {}, apiKey);
  const branches = branchesRes.branches ?? [];
  const defaultBranch = findDefaultBranch(branches);
  if (!defaultBranch) {
    const seen = branches
      .map((branch) => `${branch.name ?? "(unnamed)"} [default: ${String(branch.default)}]`)
      .join(", ");
    throw new Error(
      `no default branch found; refusing to guess where to fork from (saw: ${seen || "no branches"})`,
    );
  }

  const branchName = `db-test-${Date.now()}`;
  let branchId;
  try {
    let created;
    try {
      created = await createBranch();
    } catch (error) {
      // Some API versions reject `expires_at` on create; fall back and PATCH it.
      if (!String(error.message).includes("expires_at")) throw error;
      created = await createBranch(/* withExpiry */ false);
      await api(
        `/projects/${projectId}/branches/${created.branch.id}`,
        { method: "PATCH", body: JSON.stringify({ branch: { expires_at: expiryStamp() } }) },
        apiKey,
      );
    }

    const branch = created.branch ?? {};
    branchId = branch.id;
    if (!branchId) throw new Error("create-branch response carried no branch id");

    if (isProtectedBranch(branch, { defaultBranchId: defaultBranch.id, defaultBranchName: defaultBranch.name })) {
      throw new Error(`refusing to proceed: the created branch ${branch.id} (${branch.name}) looks like a protected branch`);
    }
    console.log(`test:db using branch ${branch.id} (${branch.name ?? "unnamed"})`);

    const unpooledUri = pickConnectionUri(created, branch);
    const pooledUri = buildPooledUri(unpooledUri);
    console.log(`test:db pooled URL host: ${new URL(pooledUri).hostname}`);

    // Empty the branch: the migrations must build the full schema from nothing.
    // Dropping `public` also drops any extensions that live there; the first
    // custom migration recreates the citext extension.
    const { Client } = await import("pg");
    const empty = new Client({ connectionString: unpooledUri });
    await empty.connect();
    try {
      await empty.query("DROP SCHEMA IF EXISTS public CASCADE");
      await empty.query("DROP SCHEMA IF EXISTS drizzle CASCADE");
      await empty.query("CREATE SCHEMA public");
    } finally {
      await empty.end();
    }

    // Migrate over the direct connection (PgBouncer breaks session state).
    const migrate = spawnSync("npx", ["--no-install", "drizzle-kit", "migrate"], {
      cwd: WEB_ROOT,
      env: { ...process.env, DATABASE_URL_UNPOOLED: unpooledUri },
      stdio: "inherit",
    });
    if (migrate.status !== 0) {
      throw new Error(`drizzle-kit migrate failed (exit ${migrate.status})`);
    }

    // Run the db tests over the pooled URL, naming the branch so the config
    // refuses to start anywhere else. The auth tests (tests/db/auth.test.ts)
    // also need app config: a per-run AUTH_SECRET (never a real value), the
    // AUTH_URL the links carry, and NODE_ENV=development — better-auth turns
    // its origin checks off under a test env (they are the forged-origin
    // tests' subject), and mail print mode must never run in production.
    const tests = spawnSync(
      "npx",
      ["--no-install", "vitest", "run", "--config", "vitest.db.config.mts"],
      {
        cwd: WEB_ROOT,
        env: {
          ...process.env,
          DATABASE_URL: pooledUri,
          NEON_TEST_BRANCH_ID: branchId,
          AUTH_SECRET: randomBytes(32).toString("hex"),
          AUTH_URL: "http://localhost:3000",
          NODE_ENV: "development",
        },
        stdio: "inherit",
      },
    );
    process.exitCode = tests.status ?? 1;
  } finally {
    if (branchId) {
      const branchInfo = { id: branchId, name: branchName };
      if (isProtectedBranch(branchInfo, { defaultBranchId: defaultBranch.id, defaultBranchName: defaultBranch.name })) {
        console.error(`test:db refusing to delete ${branchId}: it looks like the default branch or dev; delete it by hand`);
        process.exitCode = 2;
      } else {
        try {
          await api(`/projects/${projectId}/branches/${branchId}`, { method: "DELETE" }, apiKey);
          console.log(`test:db deleted branch ${branchId}`);
        } catch (error) {
          const message = String(error.message);
          if (message.includes("404")) {
            console.log(`test:db branch ${branchId} was already gone`);
          } else {
            console.error(`test:db could not delete ${branchId}:`, error);
            process.exitCode = 1;
          }
        }
      }
    }
  }

  async function createBranch(withExpiry = true) {
    const branch = { name: branchName, parent_id: defaultBranch.id, init_source: "schema-only" };
    if (withExpiry) branch.expires_at = expiryStamp();
    return api(
      `/projects/${projectId}/branches`,
      { method: "POST", body: JSON.stringify({ branch, endpoints: [{ type: "read_write" }] }) },
      apiKey,
    );
  }
}

function pickConnectionUri(created, branch) {
  if (created.connection_uris?.length) {
    const uri = created.connection_uris[0].connection_uri;
    if (uri) return uri;
  }
  const endpoint = created.endpoints?.[0];
  const role = created.roles?.[0];
  const parameters = created.connection_uris?.[0]?.connection_parameters;
  const databaseName = parameters?.database ?? branch.database_name ?? "neondb";
  if (role?.password) {
    return buildUriFromParts({
      endpointHost: endpoint?.host ?? parameters?.host,
      roleName: role.name ?? parameters?.role ?? "neondb_owner",
      rolePassword: role.password,
      databaseName,
    });
  }
  throw new Error(
    "create-branch response had no connection URI and no role password; cannot build a connection string",
  );
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  main().catch((error) => {
    console.error("test:db failed:", error);
    process.exitCode = 1;
  });
}
#!/usr/bin/env node
// `node scripts/first-admin.mjs <email> [name]`, with DATABASE_URL in the
// environment (decision 1, review item 6).
//
// The first-admin mechanism, and never a route. It does only the database
// part: upsert the user to role `admin` through the existing neon-http client
// — insert on missing, promote on existing, idempotent. It writes no token and
// no `verification` row: Better Auth stays in charge of tokens. The password
// is set through the running app's /forgot-password, whose link prints in dev
// (print mode) and emails once H07 (Resend domain) is done. The passwordless
// admin row is harmless: nothing can sign in with it until a password is set.
//
// Plain JavaScript on purpose: it can't import the TypeScript lib/auth.ts
// (no tsx in the project), and it doesn't need to — tokens are not its job.
// The pure helpers below are imported by the offline unit test.

import { neon } from "@neondatabase/serverless";
import { pathToFileURL } from "node:url";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** argv = process.argv.slice(2); email lowercased/trimmed, name joined. */
export function parseArgs(argv) {
  const [rawEmail, ...rest] = argv;
  const email = typeof rawEmail === "string" ? rawEmail.trim().toLowerCase() : "";
  const name = rest.filter((part) => typeof part === "string" && part.trim()).join(" ") || null;
  return { email, name };
}

/**
 * The upsert: insert role 'admin' on missing, promote on existing. On re-runs
 * it never duplicates and never demotes; name is only written when given, so a
 * bare re-run doesn't wipe a name the user later set.
 */
export function buildUpsertSql(email, name) {
  const hasName = Boolean(name);
  const cols = hasName ? ["email", "name", "role"] : ["email", "role"];
  const values = hasName ? [email, name, "admin"] : [email, "admin"];
  const placeholders = values.map((_, i) => `$${i + 1}`).join(", ");
  const set = hasName ? ["role = excluded.role", "name = excluded.name"] : ["role = excluded.role"];
  return {
    text: `insert into users (${cols.join(", ")}) values (${placeholders}) \
on conflict (email) do update set ${set.join(", ")} returning id, email, role`,
    values,
  };
}

/**
 * Run the upsert through a neon-http client and return the first row (or null).
 * Exported for the offline test, which stubs the client so the call shape is
 * covered without Neon (code review round 1 finding 1): the 1.x driver only
 * accepts the parameterised form `client.query(text, values)` — calling the
 * driver itself as a plain function is refused before any network call.
 */
export async function runUpsert(client, email, name) {
  const { text, values } = buildUpsertSql(email, name);
  const rows = await client.query(text, values);
  return rows?.[0] ?? null;
}

async function main() {
  if (!process.env.DATABASE_URL) {
    console.error("first-admin needs DATABASE_URL in the environment (locally: `neon checkout dev`).");
    process.exit(2);
  }
  const { email, name } = parseArgs(process.argv.slice(2));
  if (!EMAIL_PATTERN.test(email)) {
    console.error("usage: node scripts/first-admin.mjs <email> [name]");
    process.exit(2);
  }
  const row = await runUpsert(neon(process.env.DATABASE_URL), email, name);
  console.log(
    row
      ? `First admin ready: ${row.email} (${row.id}) now has role '${row.role}'.`
      : "Upsert ran but returned no row (unexpected).",
  );
  console.log(
    "Set the password through the running app: open /forgot-password and enter the email. " +
      "The link prints in dev (print mode); once H07's Resend domain is verified it emails instead. " +
      "The script wrote no token — Better Auth issues the one-time link.",
  );
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  main().catch((error) => {
    console.error("first-admin failed:", error);
    process.exitCode = 1;
  });
}